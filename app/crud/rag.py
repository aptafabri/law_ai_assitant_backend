import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain_community.llms import OpenAI
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.vectorstores.pinecone import Pinecone as PineconeLangChain
from langchain_core.chat_history import BaseChatMessageHistory
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain.retrievers.multi_query import MultiQueryRetriever
from core.config import settings
from pinecone import Pinecone
import langchain
langchain.debug = True

pc = Pinecone( api_key=settings.PINECONE_API_KEY )

session_store = {}

def run_llm_conversational_retrievalchain_with_sourcelink(question: str, session_id: str = None):
    """
    making answer witn relevant documents and custom prompt with memory(chat_history) and source link..
    """
        
    qa_prompt_template = """"
            #### Instruction #####
            You are a trained bot to guide people about Turkish Law and your name is AdaletGPT.
            Given the following conversation and pieces of context, create the final answer the question at the end.\n
            If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
            You must answer in turkish.
            If you find the answer, write the answer in copious and add the list of source file name that are **directly** used to derive the final answer.\n
            Don't include the source file names that are irrelevant to the final answer.\n
            If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct.\n
            If you don't know the answer to a question, please don't share false information.\n
            
            QUESTION : {question}\n
            
            =================
            CONTEXT : {context}\n
            CONVERSATION: {chat_history}\n
            =================
            
            FINAL ANSWER:
                              
    """

    QA_CHAIN_PROMPT = PromptTemplate.from_template(qa_prompt_template) # prompt_template defined above
    
    ######  Setting Multiquery retriever as base retriver ######
    QUERY_PROMPT = PromptTemplate(
        input_variables=["question"],
        template="""You are an AI language model assistant. Your task is 
        to generate 3 different versions of the given user question in turkish
        to retrieve relevant documents from a vector  database. 
        By generating multiple perspectives on the user question, 
        your goal is to help the user overcome some of the limitations 
        of distance-based similarity search. Provide these alternative 
        questions separated by newlines. Original question: {question}""",
    )

    llm = ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0)


    document_llm_chain = LLMChain(
        llm=llm,
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
    
    question_prompt_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question in its origin language, if the follow up question is already a standalone question, just return the follow up question.

    Chat History:
    {chat_history}
    Follow Up question: {question}
    Standalone question:
    """

    condense_question_prompt = PromptTemplate.from_template(question_prompt_template)

  
    question_generator_chain = LLMChain(llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt=condense_question_prompt)

    memory = ConversationSummaryBufferMemory(
        llm=llm,
        memory_key= "chat_history",
        return_messages= "on",
        chat_memory=PostgresChatMessageHistory(
            connection_string=settings.POSGRES_CHAT_HISTORY_URI,
            session_id=session_id
        ),
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

    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}), llm=llm, prompt = QUERY_PROMPT
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa = ConversationalRetrievalChain(
        combine_docs_chain= combine_documents_chain,
        question_generator= question_generator_chain,
        callbacks=None,
        verbose=False,
        retriever=compression_retriever,
        return_source_documents=False,
        memory= memory
    )  

    return qa.invoke({"question": question})

def run_llm_conversational_retrievalchain_without_sourcelink(question: str, session_id: str = None):

    qa_prompt_template = """"
            You are a trained bot to guide people about Turkish Law and your name is AdaletGPT.
            Use the following conversation and context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
            You must answer in turkish.

            Context: {context} \n
            Conversation: {chat_history} \n

            Question : {question}\n
            Helpful Answer:   
    """

    llm = ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0)
    
    QA_CHAIN_PROMPT = PromptTemplate.from_template(qa_prompt_template) # prompt_template defined above
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        
    docsearch = PineconeLangChain.from_existing_index(
        embedding=embeddings,
        index_name=settings.INDEX_NAME,
    )

    ######  Setting Multiquery retriever as base retriver ######
    QUERY_PROMPT = PromptTemplate(
        input_variables=["question"],
        template="""You are an AI language model assistant. Your task is 
        to generate 3 different versions of the given user question in turkish
        to retrieve relevant documents from a vector  database. 
        By generating multiple perspectives on the user question, 
        your goal is to help the user overcome some of the limitations 
        of distance-based similarity search. Provide these alternative 
        questions separated by newlines. Original question: {question}""",
    )

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

    question_prompt_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, if the follow up question is already a standalone question, just return the follow up question.
    
    Chat History:
    {chat_history}
    Follow Up question: {question}
    Standalone question:
    """

    condense_question_prompt = PromptTemplate.from_template(question_prompt_template)

  
    question_generator_chain = LLMChain(llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt=condense_question_prompt)


    base_retriever = MultiQueryRetriever.from_llm(
        retriever=docsearch.as_retriever(search_kwargs={"k": 50}), llm=llm, prompt = QUERY_PROMPT
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )
    # reranked_docs = compression_retriever.get_relevant_documents(query= question)
    # print("Multiquery retriever doc count:", len(reranked_docs))
    # print("Source Documents:", reranked_docs)
   

    memory = ConversationSummaryBufferMemory(
        llm=llm, 
        memory_key= "chat_history",
        return_messages= "on",
        chat_memory=PostgresChatMessageHistory(
            connection_string=settings.POSGRES_CHAT_HISTORY_URI,
            session_id=session_id
        ),
        max_token_limit=3000,
        output_key = "answer",
        ai_prefix="Question",
        human_prefix="Answer"
    )
    
    # qa = ConversationalRetrievalChain.from_llm(
    #     llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature= 0.2),
    #     retriever=compression_retriever,
    #     return_source_documents=True,
    #     condense_question_llm= ChatOpenAI(model_name="gpt-4-1106-preview"),
    #     combine_docs_chain_kwargs={"prompt":QA_CHAIN_PROMPT},
    #     memory = memory
    # )

    qa = ConversationalRetrievalChain(
        combine_docs_chain= combine_documents_chain,
        question_generator= question_generator_chain,
        callbacks=None,
        verbose=False,
        retriever=compression_retriever,
        return_source_documents=True,
        memory= memory
    )  

    
    return qa.invoke({"question": question})

# def run_llm_conversational_retrievalchain(question: str, chat_history: List[Dict[str, Any]] = []):
#     """
#     making answer witn relevant documents and custom prompt with memory(chat_history)
#     """
#     custom_prompt_template = """"[INST] <<SYS>>
#     You are a trained bot to guide people about Turkish Law. You will answer user's query with your knowledge and the context provided.\n
#     Use the following pieces of context to answer the question at the end.\n If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
#     If there is no full data for the question at the end, just say that you don't know.\n
#     You must answer in turkish about all questions.\n
#     You must add full sources.
#     If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.\n
#     Do not say thank you and tell you are an AI Assistant and be open about everything.\n
#     <</SYS>>
#     Use the following pieces of context to answer the users question.\n
#     Context : {context}
#     Question : {question}
#     Answer : [/INST]
#     """

#     prompt = PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])

#     embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
#     chat = ChatOpenAI(
#         model_name = 'gpt-3.5-turbo-16k',
#         verbose=True,
#         temperature=0,
#     )
    
#     docsearch = PineconeLangChain.from_existing_index(
#         embedding=embeddings,
#         index_name=INDEX_NAME,
#     )

#     qa = ConversationalRetrievalChain.from_llm(
#         llm=chat,
#         retriever=docsearch.as_retriever(search_kwargs={"k": 4}),
#         return_source_documents=True,
#         combine_docs_chain_kwargs={"prompt":prompt}
#     )

    
#     return qa.invoke({"question": question, "chat_history": chat_history})


# def run_llm_retrieval_qa(query: str):
#     """
#     We can't use memory in retreivalqa chain...
#     making answer witn relevant documents and custom prompt without memory(chat_history)
#     """
#     embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
#     docsearch = PineconeLangChain.from_existing_index(
#         embedding=embeddings,
#         index_name=settings.INDEX_NAME
#     )
#     chat = ChatOpenAI(
#         verbose=True,
#         temperature=0,
#     )
    
#     qa= RetrievalQA.from_chain_type(
        
#         llm=chat,
#         chain_type="stuff",
#         retriever=docsearch.as_retriever(search_kwargs={'k': 2}),
#         return_source_documents=True,
#         chain_type_kwargs={'prompt':prompt}
#     )
    
#     answer= qa.invoke({"query":query})
    
#     return answer['result']