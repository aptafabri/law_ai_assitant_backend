import os
import sys
import asyncio
from dotenv import load_dotenv
import json
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
from crud.classify import Classifier
from crud.chat import (
    add_legal_chat_message,
    add_legal_session_summary,
    legal_session_exist,
    init_postgres_chat_memory,
    summarize_session_streaming,
)
from log_config import configure_logging

# Loading environment variables
load_dotenv()

# Configure logging
logger = configure_logging()

# Setup OpenAI model and embeddings
logger.info("Setting up OpenAI models and embeddings")
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

# Initialize Classifier
logger.info("Initializing namespace classifier")
namespace_classifier = Classifier()

# Define callback handler for queue
class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        logger.debug("LLM process ended streaming.")
        return self.done.set()


@traceable(run_type="llm", name="RAG with Legal Cases", project_name="adaletgpt")
def rag_chat(question: str, session_id: str = None):
    logger.info(f"Starting RAG chat for question: {question}")

    try:
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
        logger.debug("Compression retriever setup completed.")

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
        logger.debug(f"Memory initialized for session {session_id}")

        qa = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=compression_retriever,
            return_source_documents=True,
            condense_question_llm=question_llm,
            combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT},
            memory=memory,
        )
        logger.info("RAG chat process completed successfully.")
        return qa.invoke({"question": question, "chat_history": []})

    except Exception as e:
        logger.error(f"Error in rag_chat: {e}")
        raise e


@traceable(run_type="llm", name="RAG streaming with Legal Cases", project_name="adaletgpt")
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
    logger.info(f"Starting RAG streaming chat for session {session_id}")
    answer_streaming_callback = QueueCallbackHandler()
    summary_streaming_callback = QueueCallbackHandler()

    try:
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
        QA_CHAIN_PROMPT = PromptTemplate.from_template(legal_chat_qa_prompt_template)

        docsearch = PineconeVectorStore(
            pinecone_api_key=settings.PINECONE_API_KEY,
            embedding=embeddings,
            index_name=settings.LEGAL_CASE_INDEX_NAME,
        )
        logger.debug(f"PineconeVectorStore initialized for session {session_id}")

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

        logger.info(f"RAG streaming chat initialized for question: {standalone_question}")
        answer_task = asyncio.create_task(
            qa.ainvoke({"question": standalone_question, "chat_history": chat_history})
        )
        answer = ""
        async for answer_token in answer_streaming_callback.aiter():
            logger.debug(f"Streaming answer token: {answer_token}")
            answer += answer_token
            data = json.dumps({"message": {"data_type": 0, "content": answer}})
            yield data

        await answer_task

        if legal_session_exist(session_id=session_id, session=db_session) == False:
            summary_task = asyncio.create_task(
                summarize_session_streaming(
                    question=question, answer=answer, llm=summary_streaming_llm
                )
            )
            summary = ""
            async for summary_token in summary_streaming_callback.aiter():
                logger.debug(f"Streaming summary token: {summary_token}")
                summary += summary_token
                data_summary = json.dumps(
                    {"message": {"data_type": 1, "content": summary}}
                )
                yield data_summary
            await summary_task

            add_legal_session_summary(
                user_id=user_id, session_id=session_id, summary=summary, session=db_session
            )
            logger.info(f"Summary added for session {session_id}")

        legal_file_data = json.dumps(
            {"message": {"data_type": 2, "content": legal_file_name}}
        )
        yield legal_file_data

        s3_key_data = json.dumps(
            {"message": {"data_type": 3, "content": legal_s3_key}}
        )
        yield s3_key_data

        await add_chat_history(
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=answer,
            legal_attached=legal_attached,
            legal_file_name=legal_file_name,
            legal_s3_key=legal_s3_key,
            db_session=db_session,
        )

    except Exception as e:
        logger.error(f"Error in rag_streaming_chat: {e}")
        raise e


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
    logger.info(f"Adding chat history for session {session_id}")
    try:
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
        logger.info(f"Chat history added successfully for session {session_id}")
    except Exception as e:
        logger.error(f"Error adding chat history: {e}")
        raise e


@traceable(run_type="llm", name="Get Relevant Legal Cases", project_name="adaletgpt")
def get_relevant_legal_cases(session_id: str):
    logger.info(f"Retrieving relevant legal cases for session {session_id}")
    try:
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
            logger.warning(f"No chat history found for session {session_id}")
            return []

        logger.debug(f"Chat history retrieved for session {session_id}: {messages['chat_history']}")
        
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
            base_compressor=compressor, base_retriever=docsearch.as_retriever(search_kwargs={"k": 50})
        )

        reranked_docs = compression_retriever.get_relevant_documents(
            query=conversation_summary
        )
        legal_case_docs: List[str] = []
        for doc in reranked_docs:
            legal_case_docs.append(doc.page_content)

        logger.info(f"Retrieved {len(legal_case_docs)} relevant legal cases for session {session_id}")
        return legal_case_docs
    except Exception as e:
        logger.error(f"Error retrieving relevant legal cases for session {session_id}: {e}")
        raise e


@traceable(
    run_type="llm",
    name="RAG regulation chat",
    project_name="adaletgpt",
)
def rag_regulation(question: str):
    logger.info(f"Starting RAG regulation chat for question: {question}")
    try:
        QA_CHAIN_PROMPT = PromptTemplate.from_template(general_chat_qa_prompt_template)

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
        condense_question_prompt = PromptTemplate.from_template(condense_question_prompt_template)
        question_generator_chain = LLMChain(llm=question_llm, prompt=condense_question_prompt)

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

        logger.info("RAG regulation chat completed successfully.")
        return qa.invoke({"question": question, "chat_history": []})

    except Exception as e:
        logger.error(f"Error during RAG regulation chat: {e}")
        raise e


@traceable(
    run_type="llm",
    name="RAG regulation chat without source",
    project_name="adaletgpt",
)
async def rag_regulation_without_source(question: str):
    logger.info(f"Starting RAG regulation chat without source for question: {question}")
    try:
        QA_CHAIN_PROMPT = PromptTemplate.from_template(
            general_chat_without_source_qa_prompt_template
        )

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

        logger.info("RAG regulation chat without source completed successfully.")
        return await qa.ainvoke({"question": question, "chat_history": []})

    except Exception as e:
        logger.error(f"Error during RAG regulation chat without source: {e}")
        raise e


@traceable(
    run_type="llm",
    name="RAG with Legal Cases with source link",
    project_name="adaletgpt",
)
async def rag_legal_source(question: str):
    logger.info(f"Starting RAG legal source process for question: {question}")
    try:
        namespace = namespace_classifier.classify(question=question)
        docsearch = PineconeVectorStore(
            pinecone_api_key=settings.PINECONE_API_KEY,
            embedding=embeddings,
            index_name=settings.LEGAL_CASE_INDEX_NAME,
            namespace=namespace
        )

        retriever_sim = docsearch.as_retriever(
            search_type="similarity", search_kwargs={"k": 10}
        )

        MULTI_QUERY_PROMPT = PromptTemplate(
            input_variables=["question"],
            template=multi_query_prompt_template,
        )

        multi_retriever = MultiQueryRetriever.from_llm(
            retriever=retriever_sim,
            llm=ChatOpenAI(model_name="gpt-4o", temperature=0, max_tokens=3000),
            prompt=MULTI_QUERY_PROMPT,
        )

        compressor = CohereRerank(top_n=6, cohere_api_key=settings.COHERE_API_KEY)
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=multi_retriever
        )

        result = await compression_retriever.ainvoke(question)
        logger.info("RAG legal source process completed successfully.")
        return result

    except Exception as e:
        logger.error(f"Error during RAG legal source: {e}")
        raise e


@traceable(
    run_type="llm",
    name="RAG with Legal Cases with source link",
    project_name="adaletgpt",
)
async def rag_legal_source_v2(question: str):
    logger.info(f"Starting RAG legal source v2 process for question: {question}")
    try:
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

        document_prompt = PromptTemplate(
            input_variables=["page_content", "source_link"],
            template="Context:\n \tContent:{page_content}\n \tSource Link:{source_link}\n\t",
        )

        question_answer_chain = create_stuff_documents_chain(
            llm=llm, prompt=qa_prompt, document_prompt=document_prompt
        )

        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

        result = await rag_chain.ainvoke({"input": question, "chat_history": []})
        logger.info("RAG legal source v2 process completed successfully.")
        return result

    except Exception as e:
        logger.error(f"Error during RAG legal source v2: {e}")
        raise e