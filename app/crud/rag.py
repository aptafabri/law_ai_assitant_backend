import os
import sys
import asyncio
from dotenv import load_dotenv
import json

load_dotenv()
from sqlalchemy.orm import Session
from typing import Any
from datetime import datetime
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain_pinecone import PineconeVectorStore
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.memory import ConversationSummaryBufferMemory
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from core.config import settings
from langsmith import traceable
from langchain.callbacks import AsyncIteratorCallbackHandler
from typing import List
from schemas.message import LegalChatAdd
from core.prompt import (
    general_chat_qa_prompt_template,
    multi_query_prompt_template,
    condense_question_prompt_template,
    summary_legal_conversation_prompt_template,
    legal_chat_qa_prompt_template,
    legal_chat_qa_prompt_template_v2,
    general_chat_without_source_qa_prompt_template,
)
from crud.chat import (
    add_legal_chat_message,
    add_legal_session_summary,
    legal_session_exist,
    init_postgres_chat_memory,
    summarize_session_streaming,
)

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"

session_store = {}

llm = ChatOpenAI(
    model_name=settings.LLM_MODEL_NAME,
    temperature=0,
    max_tokens=3000,
)
question_llm = ChatOpenAI(
    model_name=settings.QUESTION_MODEL_NAME,
    temperature=0.3,
    max_tokens=3000,
)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        print("ended streaming")
        return self.done.set()


@traceable(run_type="llm", name="RAG with Legal Cases", project_name="adaletgpt")
def rag_chat(question: str, session_id: str = None):

    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        legal_chat_qa_prompt_template
    )  # prompt_template

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
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

    qa = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=compression_retriever,
        return_source_documents=True,
        condense_question_llm=question_llm,
        combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT},
        memory=memory,
    )
    return qa.invoke({"question": question, "chat_history": []})


@traceable(
    run_type="llm", name="RAG streaming with Legal Cases", project_name="adaletgpt"
)
async def rag_streaming_chat(
    standalone_question: str,
    question: str,
    user_id: int,
    session_id: str,
    legal_attached: bool,
    legal_s3_key: str,
    legal_file_name: str,
    chat_history: Any = [],
    db_session: Session = None,
):

    answer_streaming_callback = QueueCallbackHandler()
    summary_streaming_callback = QueueCallbackHandler()
    streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[answer_streaming_callback],
        temperature=0,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
    )
    summary_streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[summary_streaming_callback],
        temperature=0,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
    )
    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        legal_chat_qa_prompt_template
    )  # prompt_template

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
    )

    qa = ConversationalRetrievalChain.from_llm(
        llm=streaming_llm,
        retriever=compression_retriever,
        return_source_documents=True,
        condense_question_llm=question_llm,
        combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT},
    )
    answer_task = asyncio.create_task(
        qa.ainvoke({"question": standalone_question, "chat_history": chat_history})
    )
    answer = ""
    async for answer_token in answer_streaming_callback.aiter():
        print("streaming answer:", answer_token)
        answer += answer_token
        data = json.dumps(
            {
                "message": {
                    "data_type": 0,
                    "content": answer,
                }
            }
        )
        yield data

    await answer_task

    """create session summary if the user is sending new chat message"""

    if legal_session_exist(session_id=session_id, session=db_session) == False:
        summary_task = asyncio.create_task(
            summarize_session_streaming(
                question=question, answer=answer, llm=summary_streaming_llm
            )
        )
        summary = ""
        async for summary_token in summary_streaming_callback.aiter():
            summary += summary_token
            print("summary streaming:", summary)
            data_summary = json.dumps(
                {
                    "message": {
                        "data_type": 1,
                        "content": summary,
                    }
                }
            )
            yield data_summary
        await summary_task

        add_legal_session_summary(
            user_id=user_id, session_id=session_id, summary=summary, session=db_session
        )

    legal_file_data = json.dumps(
        {
            "message": {
                "data_type": 2,
                "content": legal_file_name,
            }
        }
    )

    yield legal_file_data

    s3_key_data = json.dumps(
        {
            "message": {
                "data_type": 3,
                "content": legal_s3_key,
            }
        }
    )

    yield s3_key_data

    add_chat_history(
        user_id=user_id,
        session_id=session_id,
        question=question,
        answer=answer,
        legal_attached=legal_attached,
        legal_file_name=legal_file_name,
        legal_s3_key=legal_s3_key,
        db_session=db_session,
    )


async def add_chat_history(
    user_id: int,
    session_id: str,
    question: str,
    answer: str,
    legal_attached: bool,
    legal_file_name: str,
    legal_s3_key: str,
    db_session: Session,
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
    created_date = datetime.now()
    user_message = LegalChatAdd(
        user_id=user_id,
        session_id=session_id,
        content=question,
        role="user",
        legal_attached=legal_attached,
        legal_file_name=legal_file_name,
        legal_s3_key=legal_s3_key,
        created_date=created_date,
    )
    ai_message = LegalChatAdd(
        user_id=user_id,
        session_id=session_id,
        content=answer,
        role="assistant",
        legal_attached=False,
        legal_file_name="",
        legal_s3_key="",
        created_date=created_date,
    )
    add_legal_chat_message(user_message, db_session)
    add_legal_chat_message(ai_message, db_session)


@traceable(run_type="llm", name="Get Relevant Legal Cases", project_name="adaletgpt")
def get_relevant_legal_cases(session_id: str):
    chat_memory = init_postgres_chat_memory(session_id=session_id)
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
    run_type="llm",
    name="RAG regulation chat",
    project_name="adaletgpt",
)
def rag_regulation(question: str):
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
        template="Context:\n \tContent:{page_content}\n \t Source Link:{source}",
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

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
        namespace="YONETMELIK",
    )

    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
        llm=ChatOpenAI(model_name="gpt-4o", temperature=0, max_tokens=3000),
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
    )

    return qa.invoke({"question": question, "chat_history": []})


@traceable(
    run_type="llm",
    name="RAG regulation chat without source",
    project_name="adaletgpt",
)
async def rag_regulation_without_source(question: str):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history) and source link..
    """

    QA_CHAIN_PROMPT = PromptTemplate.from_template(
        general_chat_without_source_qa_prompt_template
    )  # prompt_template defined above

    ######  Setting Multiquery retriever as base retriver ######
    QUERY_PROMPT = PromptTemplate(
        input_variables=["question"],
        template=multi_query_prompt_template,
    )

    condense_question_prompt = PromptTemplate.from_template(
        condense_question_prompt_template
    )

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
        namespace="YONETMELIK",
    )

    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}),
        llm=ChatOpenAI(model_name="gpt-4o", temperature=0, max_tokens=3000),
        prompt=QUERY_PROMPT,
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=compression_retriever,
        return_source_documents=False,
        condense_question_prompt=condense_question_prompt,
        condense_question_llm=question_llm,
        verbose=False,
        combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT},
    )

    return await qa.ainvoke({"question": question, "chat_history": []})


@traceable(
    run_type="llm",
    name="RAG with Legal Cases with source link",
    project_name="adaletgpt",
)
async def rag_legal_source(question: str):

    QA_CHAIN_PROMPT = PromptTemplate.from_template(legal_chat_qa_prompt_template)
    document_llm_chain = LLMChain(llm=llm, prompt=QA_CHAIN_PROMPT, verbose=False)
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source_link"],
        template="Context:\n \tContent:{page_content}\n \tSource Link:{source_link}\n\t",
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

    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )
    qa = ConversationalRetrievalChain(
        combine_docs_chain=combine_documents_chain,
        question_generator=question_generator_chain,
        verbose=False,
        retriever=docsearch.as_retriever(search_kwargs={"k": 6}),
        return_source_documents=False,
    )

    return await qa.ainvoke({"question": question, "chat_history": []})


@traceable(
    run_type="llm",
    name="RAG with Legal Cases with source link",
    project_name="adaletgpt",
)
async def rag_legal_source_v2(question: str):

    # Contextualize question
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, just "
        "reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    docsearch = PineconeVectorStore(
        pinecone_api_key=settings.PINECONE_API_KEY,
        embedding=embeddings,
        index_name=settings.LEGAL_CASE_INDEX_NAME,
    )
    retriever = docsearch.as_retriever(search_kwargs={"k": 6})
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", legal_chat_qa_prompt_template_v2),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    # Below we use create_stuff_documents_chain to feed all retrieved context
    # into the LLM. Note that we can also use StuffDocumentsChain and other
    # instances of BaseCombineDocumentsChain.
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source_link"],
        template="Context:\n \tContent:{page_content}\n \tSource Link:{source_link}\n\t",
    )
    question_answer_chain = create_stuff_documents_chain(
        llm=llm, prompt=qa_prompt, document_prompt=document_prompt
    )
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    return await rag_chain.ainvoke({"input": question, "chat_history": []})
