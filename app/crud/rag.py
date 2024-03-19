import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.vectorstores.pinecone import Pinecone as PineconeLangChain
from pinecone import Pinecone

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
INDEX_NAME=os.getenv("INDEX_NAME")

pc = Pinecone( api_key= PINECONE_API_KEY )

custom_prompt_template = """"[INST] <<SYS>>
You are a trained bot to guide people about turkish Law. You will answer user's query with your knowledge and the context provided. 
If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.
Do not say thank you and tell you are an AI Assistant and be open about everything.
<</SYS>>
Use the following pieces of context to answer the users question.
Context : {context}
Question : {question}
Answer : [/INST]
"""

prompt = PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])



def run_llm_conversational_retrievalchain(query: str, chat_history: List[Dict[str, Any]] = []):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history)
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

    qa = ConversationalRetrievalChain.from_llm(
        llm=chat,
        retriever=docsearch.as_retriever(),
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt":prompt}
    )
    return qa.invoke({"question": query, "chat_history": chat_history})
    

def run_llm_retrieval_qa(query: str):
    """
    We can't use 
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
