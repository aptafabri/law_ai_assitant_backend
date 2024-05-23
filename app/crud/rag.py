import os
import sys
import asyncio
from dotenv import load_dotenv
import json

load_dotenv()
from sqlalchemy.orm import Session
from typing import AsyncIterable, Any
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain_community.llms import OpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.memory import ConversationSummaryBufferMemory
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain.retrievers.multi_query import MultiQueryRetriever
from core.config import settings
from langchain_postgres import PostgresChatMessageHistory
from langsmith import traceable
from crud.chat_general import init_postgres_chat_memory
from langchain.callbacks import AsyncIteratorCallbackHandler
from crud.chat_general import (
    add_message,
    summarize_session,
    summarize_session_streaming,
    add_session_summary,
    session_exist,
    init_postgres_chat_memory,
)
from crud.chat_legal import (
    init_postgres_legal_chat_memory,
    upload_legal_description,
    read_pdf,
)
import langchain
from typing import List
from schemas.message import ChatRequest, ChatAdd, LegalChatAdd
from core.prompt import (
    general_chat_qa_prompt_template,
    multi_query_prompt_template,
    condense_question_prompt_template,
    summary_legal_conversation_prompt_template,
    legal_chat_qa_prompt_template,
)

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"

session_store = {}

llm = ChatOpenAI(model_name=settings.LLM_MODEL_NAME, temperature=0.2, max_tokens=3000)
question_llm = ChatOpenAI(
    model_name=settings.QUESTION_MODEL_NAME, temperature=0.2, max_tokens=3000
)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        print("ended streaming")

        return self.done.set()


@traceable(run_type="llm", name="RAG with source link", project_name="adaletgpt")
def rag_general_chat(question: str, session_id: str = None):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history) and source link..
    """

    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        general_chat_qa_prompt_template
    )  # prompt_template defined above

    ######  Setting Multiquery retriever as base retriver ######
    QUERY_PROMPT = PromptTemplate(
        input_variables=["question"],
        template=multi_query_prompt_template,
    )

    document_llm_chain = LLMChain(llm=llm, prompt=QA_CHAIN_PROMPT, verbose=False)
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source"],
        template="Context:\n Content:{page_content}\n Source File Name:{source}",
    )
    combine_documents_chain = StuffDocumentsChain(
        llm_chain=document_llm_chain,
        document_variable_name="context",
        document_prompt=document_prompt,
    )
    condense_question_prompt = PromptTemplate.from_template(
        condense_question_prompt_template
    )

    question_generator_chain = LLMChain(
        llm=question_llm, prompt=condense_question_prompt
    )

    chat_memory = init_postgres_chat_memory(session_id=session_id)

    memory = ConversationSummaryBufferMemory(
        llm=llm,
        memory_key="chat_history",
        return_messages="on",
        chat_memory=chat_memory,
        max_token_limit=3000,
        output_key="answer",
        ai_prefix="Question",
        human_prefix="Answer",
    )

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
    )

    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
        llm=ChatOpenAI(
            model_name="gpt-4-1106-preview", temperature=0.2, max_tokens=3000
        ),
        prompt=QUERY_PROMPT,
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa = ConversationalRetrievalChain(
        combine_docs_chain=combine_documents_chain,
        question_generator=question_generator_chain,
        verbose=False,
        retriever=compression_retriever,
        return_source_documents=False,
        memory=memory,
    )

    return qa.invoke({"question": question})


@traceable(run_type="llm", name="RAG with Legal Cases", project_name="adaletgpt")
def rag_legal_chat(question: str, session_id: str = None):

    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        legal_chat_qa_prompt_template
    )  # prompt_template

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )

    # #####  Setting Multiquery retriever as base retriver ######
    # QUERY_PROMPT = PromptTemplate(
    #     input_variables=["question"],
    #     template="""You are an AI language model assistant.\n
    #     Your task is to generate 3 different versions of the given user question in turkish to retrieve relevant documents from a vector  database.\n
    #     By generating multiple perspectives on the user question, your goal is to help the user overcome some of the limitations of distance-based similarity search.\n
    #     Provide these alternative questions separated by newlines.\n

    #     Original question: {question}""",
    # )
    # base_retriever = MultiQueryRetriever.from_llm(
    #     retriever=docsearch.as_retriever(search_kwargs={"k": 50}), llm= ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt = QUERY_PROMPT
    # )
    compressor = CohereRerank(top_n=4, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
    )
    chat_memory = init_postgres_legal_chat_memory(session_id=session_id)
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        memory_key="chat_history",
        return_messages="on",
        chat_memory=chat_memory,
        max_token_limit=3000,
        output_key="answer",
        ai_prefix="Question",
        human_prefix="Answer",
    )

    qa = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=compression_retriever,
        return_source_documents=True,
        condense_question_llm=question_llm,
        combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT},
        memory=memory,
    )
    return qa.invoke({"question": question, "chat_history": []})


@traceable(run_type="llm", name="Get Relevant Legal Cases", project_name="adaletgpt")
def get_relevant_legal_cases(session_id: str):
    chat_memory = init_postgres_legal_chat_memory(session_id=session_id)
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        memory_key="chat_history",
        chat_memory=chat_memory,
        max_token_limit=3000,
        return_messages=False,
        output_key="answer",
        ai_prefix="AI",
        human_prefix="Human",
    )
    messages = memory.load_memory_variables({})
    if messages["chat_history"] == "":
        return []
    print("chat_history", messages["chat_history"])
    prompt = PromptTemplate(
        input_variables=["conversation"],
        template=summary_legal_conversation_prompt_template,
    )

    llm_chain = LLMChain(llm=llm, prompt=prompt)

    response = llm_chain.invoke({"conversation": messages["chat_history"]})
    conversation_summary = response["text"]
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )

    # MULTI_QUERY_PROMPT = PromptTemplate(
    #     input_variables=["question"],
    #     template="""You are an AI language model assistant.\n
    #     Your task is to generate 3 different versions of the given legal case summary in turkish to retrieve relevant documents from a vector  database.\n
    #     By generating multiple perspectives on the legal case summary, your goal is to help the user overcome some of the limitations of distance-based similarity search.\n
    #     Provide these alternative legal case summary separated by newlines.\n
    #     Original Legal Case Summary: {question}""",
    # )

    # base_retriever = MultiQueryRetriever.from_llm(
    #     retriever=docsearch.as_retriever(search_kwargs={"k": 50}), llm= ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt = MULTI_QUERY_PROMPT
    # )

    compressor = CohereRerank(top_n=5, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
    )

    reranked_docs = compression_retriever.get_relevant_documents(
        query=conversation_summary
    )
    legal_caese_docs: List[str] = []
    for doc in reranked_docs:
        legal_caese_docs.append(doc.page_content)

    return legal_caese_docs


@traceable(
    run_type="llm", name="RAG Test without source link", project_name="adaletgpt"
)
async def rag_streaming_chat(
    question: str,
    user_id: int,
    session_id: str = None,
    chat_history: Any = [],
    db_session: Session = None,
):

    answer_streaming_callback = QueueCallbackHandler()
    summary_streaming_callback = QueueCallbackHandler()
    streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[answer_streaming_callback],
        temperature=0.3,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
    )
    summary_streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[summary_streaming_callback],
        temperature=0.3,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
    )
    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        general_chat_qa_prompt_template
    )  # prompt_template defined above

    ######  Setting Multiquery retriever as base retriver ######
    QUERY_PROMPT = PromptTemplate(
        input_variables=["question"],
        template=multi_query_prompt_template,
    )

    document_llm_chain = LLMChain(
        llm=streaming_llm, prompt=QA_CHAIN_PROMPT, callbacks=None, verbose=False
    )
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source"],
        template="Context:\n Content:{page_content}\n Source File Name:{source}",
    )
    combine_documents_chain = StuffDocumentsChain(
        llm_chain=document_llm_chain,
        document_variable_name="context",
        document_prompt=document_prompt,
        callbacks=None,
    )

    condense_question_prompt = PromptTemplate.from_template(
        condense_question_prompt_template
    )

    question_generator_chain = LLMChain(
        llm=question_llm, prompt=condense_question_prompt
    )
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
    )

    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
        llm=ChatOpenAI(
            model_name="gpt-4-1106-preview", temperature=0.2, max_tokens=3000
        ),
        prompt=QUERY_PROMPT,
    )

    compressor = CohereRerank(top_n=4, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa = ConversationalRetrievalChain(
        combine_docs_chain=combine_documents_chain,
        question_generator=question_generator_chain,
        verbose=False,
        retriever=compression_retriever,
        return_source_documents=True,
    )

    answer_task = asyncio.create_task(
        qa.ainvoke({"question": question, "chat_history": chat_history})
    )
    answer = ""
    async for answer_token in answer_streaming_callback.aiter():
        print("streaming answer:", answer_token)
        answer += answer_token
        data = json.dumps(
            {
                "data_type": 0,
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "answer": answer_token,
            }
        )
        yield f"{data}\n\n"
        
    await answer_task

    """create session summary if the user is sending new chat message"""
    print(
        "Session exist status:",
        session_exist(session_id=session_id, session=db_session),
    )
    if session_exist(session_id=session_id, session=db_session) == False:
        summary_task = asyncio.create_task(
            summarize_session_streaming(
                question=question, answer=answer, llm=summary_streaming_llm
            )
        )
        summary = ""
        async for summary_token in summary_streaming_callback.aiter():
            print("summary streaming:", summary_token)
            summary += summary_token
            data=json.dumps(
                {
                    "data_type": 1,
                    "user_id": user_id,
                    "session_id": session_id,
                    "summary": summary_token,
                }
            )
            yield f"{data}\n\n"
        await summary_task
        add_session_summary(
            user_id=user_id, session_id=session_id, summary=summary, session=db_session
        )

    add_chat_history(
        user_id=user_id,
        session_id=session_id,
        question=question,
        answer=answer,
        db_session=db_session,
    )


def add_chat_history(
    user_id: int, session_id: str, question: str, answer: str, db_session
):
    """add chat history for memory management"""
    chat_memory = init_postgres_chat_memory(session_id=session_id)
    memory = ConversationSummaryBufferMemory(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0.2),
        memory_key="chat_history",
        return_messages=True,
        chat_memory=chat_memory,
        max_token_limit=3000,
        output_key="answer",
        ai_prefix="Question",
        human_prefix="Answer",
    )
    memory.save_context({"input": question}, {"answer": answer})
    """ add session messages to database"""
    created_date = datetime.now()
    user_message = ChatAdd(
        user_id=user_id,
        session_id=session_id,
        content=question,
        role="user",
        created_date=created_date,
    )
    ai_message = ChatAdd(
        user_id=user_id,
        session_id=session_id,
        content=answer,
        role="assistant",
        created_date=created_date,
    )

    add_message(user_message, db_session)
    add_message(ai_message, db_session)
