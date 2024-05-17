import os
from dotenv import load_dotenv

load_dotenv()
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
from crud.chat_legal import (
    init_postgres_legal_chat_memory,
    upload_legal_description,
    read_pdf,
)
import langchain
from typing import List

langchain.debug = True
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
llm = ChatOpenAI(model_name=settings.LLM_MODEL_NAME, temperature=0)
question_llm = ChatOpenAI(model_name=settings.QUESTION_MODEL_NAME, temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


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

    document_llm_chain = LLMChain(
        llm=llm, prompt=QA_CHAIN_PROMPT, callbacks=None, verbose=False
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
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        prompt=QUERY_PROMPT,
    )

    compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa = ConversationalRetrievalChain(
        combine_docs_chain=combine_documents_chain,
        question_generator=question_generator_chain,
        callbacks=None,
        verbose=False,
        retriever=compression_retriever,
        return_source_documents=False,
        memory=memory,
    )
    return qa.invoke({"question": question})


# @traceable(
#     run_type= "llm",
#     name = "RAG Test without source link",
#     project_name= "adaletgpt"
# )
# def rag_test_chat(question: str, session_id: str = None):

#     qa_prompt_template = """"
#     You are a trained bot to guide people about Turkish Law and your name is AdaletGPT.
#     Use the following conversation and context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
#     You must answer in turkish.

#     Context: {context} \n
#     Conversation: {chat_history} \n

#     Question : {question}\n
#     Helpful Answer:
#     """

#     document_llm = ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0)
#     question_generator_llm =  ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0.8)

#     QA_CHAIN_PROMPT = PromptTemplate.from_template(qa_prompt_template) # prompt_template defined above

#     embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

#     docsearch = PineconeVectorStore.from_existing_index(
#         embedding=embeddings,
#         index_name=settings.INDEX_NAME,
#     )

#     ######  Setting Multiquery retriever as base retriver ######
#     QUERY_PROMPT = PromptTemplate(
#         input_variables=["question"],
#         template="""You are an AI language model assistant.\n
#         Your task is to generate 3 different versions of the given user question in turkish to retrieve relevant documents from a vector  database.\n
#         By generating multiple perspectives on the user question, your goal is to help the user overcome some of the limitations of distance-based similarity search.\n
#         Provide these alternative questions separated by newlines.\n

#         Original question: {question}""",
#     )

#     document_llm_chain = LLMChain(
#         llm=document_llm,
#         prompt=QA_CHAIN_PROMPT,
#         callbacks=None,
#         verbose=False
#     )
#     document_prompt = PromptTemplate(
#         input_variables=["page_content", "source"],
#         template="Context:\n Content:{page_content}\n Source File Name:{source}",
#     )

#     combine_documents_chain = StuffDocumentsChain(
#         llm_chain=document_llm_chain,
#         document_variable_name="context",
#         document_prompt=document_prompt,
#         callbacks=None,
#     )

#     question_prompt_template = """"Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.

#     Chat History:
#     {chat_history}
#     Follow Up question: {question}
#     Standalone question:
#     """

#     condense_question_prompt = PromptTemplate.from_template(question_prompt_template)


#     question_generator_chain = LLMChain(llm=question_generator_llm, prompt=condense_question_prompt)


#     base_retriever = MultiQueryRetriever.from_llm(
#         retriever=docsearch.as_retriever(search_kwargs={"k": 50}), llm= ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0), prompt = QUERY_PROMPT
#     )

#     compressor = CohereRerank(top_n=10, cohere_api_key=settings.COHERE_API_KEY)
#     compression_retriever = ContextualCompressionRetriever(
#         base_compressor=compressor, base_retriever=base_retriever
#     )

#     chat_memory = init_postgres_chat_memory(session_id= session_id)
#     memory = ConversationSummaryBufferMemory(
#         llm= ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
#         memory_key= "chat_history",
#         return_messages= True,
#         chat_memory=chat_memory,
#         max_token_limit=3000,
#         output_key = "answer",
#         ai_prefix="Question",
#         human_prefix="Answer"
#     )

#     qa = ConversationalRetrievalChain(
#         combine_docs_chain= combine_documents_chain,
#         question_generator= question_generator_chain,
#         callbacks=None,
#         verbose=False,
#         retriever=compression_retriever,
#         return_source_documents=True,
#         memory= memory
#     )


#     return qa.invoke({"question": question})


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

    docsearch = PineconeLangChain.from_existing_index(
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
