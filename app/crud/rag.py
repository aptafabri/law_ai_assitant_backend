import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.chains.qa_with_sources.retrieval import RetrievalQAWithSourcesChain
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain_community.llms import OpenAI
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.vectorstores.pinecone import Pinecone as PineconeLangChain
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.memory import ChatMessageHistory
from langchain.memory import ConversationSummaryBufferMemory, ConversationBufferMemory
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from core.config import settings
from pinecone import Pinecone
import langchain
langchain.debug = True

pc = Pinecone( api_key=settings.PINECONE_API_KEY )

session_store = {}

def get_session_history(session_id: str = None ) -> BaseChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = PostgresChatMessageHistory(
            connection_string=settings.SQLALCHEMY_DATABASE_URI,
            session_id=session_id
        )
    return session_store[session_id]

def run_llm_conversational_retrievalchain_with_sourcelink(question: str, session_id: str = None):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history) and source link..
    """
        
    qa_prompt_template = """"
            #### Instruction #####
            You are a trained bot to guide people about Turkish Law and your name is AdaletGPT Assistant.
            Given the following pieces of context and conversations, create the final answer the question at the end.\n
            If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
            You must answer in turkish.
            If you find the answer, write the answer in copious and add the list of source file name that are **directly** used to derive the final answer.\n
            Don't include the source file names that are irrelevant to the final answer.\n
            If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct.\n
            If you don't know the answer to a question, please don't share false information.\n
            Use as much detail as possible when responding and try to make answer in markdown format as much as possible.\n
            
            QUESTION : {question}\n
            
            =================
            CONTEXT : {context}\n
            CONVESATION: {chat_history}\n
            =================
            
            FINAL ANSWER:        
                       
    """

    QA_CHAIN_PROMPT = PromptTemplate.from_template(qa_prompt_template) # prompt_template defined above
    
    document_llm_chain = LLMChain(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        prompt=QA_CHAIN_PROMPT,
        callbacks=None,
        verbose=False
    )
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source"],
        template="Context:\ncontent:{page_content}\nsource file name:{source}",
    )

    combine_documents_chain = StuffDocumentsChain(
        llm_chain=document_llm_chain,
        document_variable_name="context",
        document_prompt=document_prompt,
        callbacks=None,
    )
    
    question_prompt_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.

    Chat History:
    {chat_history}
    Follow Up question: {question}
    Standalone question:
    """

    condense_question_prompt = PromptTemplate.from_template(question_prompt_template)

  
    question_generator_chain = LLMChain(llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt=condense_question_prompt)


    memory = ConversationSummaryBufferMemory(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        memory_key= "chat_history",
        return_messages= "on",
        chat_memory=get_session_history(session_id),
        max_token_limit=3000,
        output_key = "answer",
        ai_prefix="Question",
        human_prefix="Answer"
    )
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        
    
    docsearch = PineconeLangChain.from_existing_index(
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
    )

    qa = ConversationalRetrievalChain(
        combine_docs_chain= combine_documents_chain,
        question_generator= question_generator_chain,
        callbacks=None,
        verbose=False,
        retriever= docsearch.as_retriever(search_kwargs={"k": 4}),
        return_source_documents=False,
        memory= memory
    )


    
    return qa.invoke({"question": question})


def run_llm_conversational_retrievalchain(question: str, chat_history: List[Dict[str, Any]] = []):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history)
    """
    custom_prompt_template = """"[INST] <<SYS>>
    You are a trained bot to guide people about Turkish Law. You will answer user's query with your knowledge and the context provided.\n
    Use the following pieces of context to answer the question at the end.\n If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
    If there is no full data for the question at the end, just say that you don't know.\n
    You must answer in turkish about all questions.\n
    You must add full sources.
    If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.\n
    Do not say thank you and tell you are an AI Assistant and be open about everything.\n
    <</SYS>>
    Use the following pieces of context to answer the users question.\n
    Context : {context}
    Question : {question}
    Answer : [/INST]
    """

    prompt = PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
    chat = ChatOpenAI(
        model_name = 'gpt-3.5-turbo-16k',
        verbose=True,
        temperature=0,
    )
    
    docsearch = PineconeLangChain.from_existing_index(
        embedding=embeddings,
        index_name=INDEX_NAME,
    )

    qa = ConversationalRetrievalChain.from_llm(
        llm=chat,
        retriever=docsearch.as_retriever(search_kwargs={"k": 4}),
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt":prompt}
    )

    
    return qa.invoke({"question": question, "chat_history": chat_history})


def run_llm_retrieval_qa(query: str):
    """
    We can't use memory in retreivalqa chain...
    making answer witn relevant documents and custom prompt without memory(chat_history)
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    docsearch = PineconeLangChain.from_existing_index(
        embedding=embeddings,
        index_name=INDEX_NAME,
    )
    chat = ChatOpenAI(
        verbose=True,
        temperature=0,
    )
    
    qa= RetrievalQA.from_chain_type(
        
        llm=chat,
        chain_type="stuff",
        retriever=docsearch.as_retriever(search_kwargs={'k': 2}),
        return_source_documents=True,
        chain_type_kwargs={'prompt':prompt}
    )
    
    answer= qa.invoke({"query":query})
    
    return answer['result']
