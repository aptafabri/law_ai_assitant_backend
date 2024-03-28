from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai.chat_models import ChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
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
from langchain.memory import ChatMessageHistory
from langchain.memory import ConversationSummaryBufferMemory, ConversationBufferMemory
from langchain_openai import OpenAI
from core import settings
from pinecone import Pinecone
import langchain
import psycopg
langchain.debug = True



pc = Pinecone( api_key= settings.PINECONE_API_KEY )

custom_prompt_template = """"
        You are a trained bot to guide people about Turkish Law. You will answer user's query with your knowledge and the context provided.\n
            Use the following pieces of context and chat history to answer the question at the end.\n If you don't know the answer, just say that you don't know, don't try to make up an answer.\n
            If you find the answer, write the answer in a concise way and add the list of source file name that are **directly** used to derive the answer. Exclude the source file names that are irrelevant to the final answer .
            If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.\n
            You must answer in turkish about all questions.\n
            Do not say thank you and tell you are an AI Assistant and be open about everything.\n
            Chat history: {chat_history}
            
            Context : {context}\n
            
            Question : {question}\n
            
            
        
        Answer : [/INST]
"""


embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
chat = ChatOpenAI(
    model_name = 'gpt-3.5-turbo-16k',
    verbose=False,
    temperature=0,
)

docsearch = PineconeLangChain.from_existing_index(
    embedding=embeddings,
    index_name=settings.INDEX_NAME,
)

QA_CHAIN_PROMPT = PromptTemplate.from_template(custom_prompt_template) # prompt_template defined above
llm_chain = LLMChain(
    llm=ChatOpenAI(model_name="gpt-4-1106-preview"),
    prompt=QA_CHAIN_PROMPT,
    callbacks=None,
    verbose=False
)
document_prompt = PromptTemplate(
    input_variables=["page_content", "source"],
    template="Context:\ncontent:{page_content}\nsource file name:{source}",
)

combine_documents_chain = StuffDocumentsChain(
        llm_chain=llm_chain,
        document_variable_name="context",
        document_prompt=document_prompt,
        callbacks=None,
    )

template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.
if a follow up question is not related with followng conversation, pass follow up question directly to standalone question 

Chat History:
{chat_history}
Follow Up question: {question}
Standalone question:
"""

question_prompt = PromptTemplate.from_template(template)
llm = OpenAI()
question_generator_chain = LLMChain(llm=ChatOpenAI(model_name="gpt-4-1106-preview"), prompt=question_prompt, verbose= True)


store = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = PostgresChatMessageHistory(
            connection_string="postgresql://postgres:postgres@localhost/chat_history",
            session_id="bbb"
        )
    return store[session_id]


# memory = ConversationSummaryBufferMemory(
#     llm=llm,
#     memory_key= "chat_history",
#     return_messages= "on",
#     chat_memory=get_session_history("aaa"),
#     max_token_limit=3000,
#     output_key = "answer"
# )

memory = ConversationBufferMemory(memory_key="chat_history", return_messages= True,output_key= 'answer')

qa = ConversationalRetrievalChain(
        combine_docs_chain= combine_documents_chain,
        question_generator= question_generator_chain,
        callbacks=None,
        verbose=True,
        retriever= docsearch.as_retriever(search_kwargs={"k": 4}),
        return_source_documents=False,
        memory= memory
)



# qa.invoke({"question": "Anayasanın 7 Maddesi nedir?"})
qa.invoke({"question": "what is your name?"})
response= qa.invoke({"question": "what ?"})
# response = qa.invoke({"question": "which was my last question?"})
# response = qa.invoke({"question": "I see"})
# response = qa.invoke({"question": "hello"})
print(response)

# with_message_history = RunnableWithMessageHistory(
#     qa,
#     get_session_history,
#     input_messages_key="question",
#     history_messages_key="chat_history",
#     output_messages_key= 'answer'
# )

# print(
#     with_message_history.invoke(
#         { "question": "Anayasanın 7 Maddesi nedir?"},
#         config={"configurable": {"session_id": "abc123"}},
#     )
# )

# print(
#     with_message_history.invoke(
#         { "question": "What?"},
#         config={"configurable": {"session_id": "abc123"}},
#     )
# )
