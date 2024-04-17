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
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from core.config import settings
from pinecone import Pinecone
import langchain
langchain.debug = False

pc = Pinecone( api_key=settings.PINECONE_API_KEY )

session_store = {}

def get_session_history(session_id: str = None ) -> BaseChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = PostgresChatMessageHistory(
            connection_string=settings.POSGRES_CHAT_HISTORY_URI,
            session_id=session_id
        )
    return session_store[session_id]

def run_llm_conversational_retrievalchain_with_sourcelink(question: str):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history) and source link..
    """
        
    qa_prompt_template = """"
            #### Instruction #####
            You are a trained bot to guide people about Turkish Law and your name is AdaletGPT.
            Given the following pieces of context and conversations, create the final answer the question at the end.\n
            If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
            You must answer in turkish.
            QUESTION : {question}\n
            
            =================
            CONTEXT : {context}\n
            CONVESATION: {chat_history}\n
            =================
            
            FINAL ANSWER:
                              
    """
    
    QA_CHAIN_PROMPT = PromptTemplate.from_template(qa_prompt_template) # prompt_template defined above
    
    # memory = ConversationSummaryBufferMemory(
    #     llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
    #     memory_key= "chat_history",
    #     return_messages= "on",
    #     chat_memory=PostgresChatMessageHistory(
    #         connection_string=settings.POSGRES_CHAT_HISTORY_URI,
    #         session_id=session_id
    #     ),
    #     max_token_limit=3000,
    #     output_key = "answer",
    #     ai_prefix="Question",
    #     human_prefix="Answer"
    # )
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        
    
    docsearch = PineconeLangChain.from_existing_index(
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
    )

    compressor = FlashrankRerank()
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=docsearch.as_retriever(search_kwargs={"k": 4})
    )

    qa = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        retriever=docsearch.as_retriever(search_kwargs={"k": 10}),
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt":QA_CHAIN_PROMPT}
    )

    
    return qa.invoke({"question": question, "chat_history":[]})


response = run_llm_conversational_retrievalchain_with_sourcelink(question="Kişisel Verilerin Korunması Kanunu'nun 31. maddesinin içeriği nedir?")

print(response["answer"])