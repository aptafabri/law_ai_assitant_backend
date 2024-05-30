import asyncio
import json
from langchain import hub
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from core.config import settings
from tools.rag_regulation_tool import rag_regulation_tool
from tools.rag_legal_tool import rag_legal_tool
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.tools.tavily_search import TavilySearchResults
from crud.chat_general import init_postgres_chat_memory
from sqlalchemy.orm import Session
from typing import AsyncIterable, Any
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.agents import (
    AgentExecutor,
    create_tool_calling_agent,
)
from crud.chat_general import (
    summarize_session,
    init_postgres_chat_memory,
)
from crud.chat_legal import (
    add_legal_session_summary,
    legal_session_exist,
)
from crud.rag import add_legal_chat_history


async def agent_run(
    standalone_question: str,
    question: str,
    user_id: int,
    session_id: str,
    legal_attached: bool,
    legal_s3_key: str,
    legal_file_name: str,
    db_session: Session = None,
):

    llm = ChatOpenAI(
        verbose=True,
        model_name=settings.LLM_MODEL_NAME,
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        streaming=True,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant and your name is AdaletGPT. Make sure to use the rag_legal and rag_regulation tools for information.\n
                Use tavily_search_result_json tool if user's question is not related with case laws, statues and judicial precedents and decisions.\n
                Use only one tool with one question.\n If you don't need tools, don't use tool
                You must answer in Turkish.
                If the question is unclear, require detailed question
                """,
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    tools = [
        rag_regulation_tool(),
        rag_legal_tool(),
        TavilySearchResults(max_results=1),
    ]

    agent = create_tool_calling_agent(llm, tools, prompt)

    """initialize session memory for agent"""
    chat_memory = init_postgres_chat_memory(session_id=session_id)
    memory = ConversationSummaryBufferMemory(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        memory_key="chat_history",
        return_messages=True,
        chat_memory=chat_memory,
        max_token_limit=3000,
        ai_prefix="Question",
        human_prefix="Answer",
    )

    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True, memory=memory
    )
    answer = ""
    async for event in agent_executor.astream_events(
        {"input": standalone_question}, version="v1"
    ):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:

                answer += content
                print("streaming_answer:", content)
                data = json.dumps(
                    {
                        "message": {
                            "data_type": 0,
                            "content": answer,
                        }
                    }
                )
                yield data

        elif kind == "on_tool_start":
            print("--")
            print(
                f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}"
            )
        elif kind == "on_tool_end":
            print(f"Done tool: {event['name']}")
            print(f"Tool output was: {event['data'].get('output')}")
            print("--")

    if legal_session_exist(session_id=session_id, session=db_session) == False:
        summary = await summarize_session(question=question, answer=answer)
        data_summary = json.dumps(
            {
                "message": {
                    "data_type": 1,
                    "content": summary,
                }
            }
        )
        yield data_summary

        await add_legal_session_summary(
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

    await add_legal_chat_history(
        user_id=user_id,
        session_id=session_id,
        question=question,
        answer=answer,
        legal_attached=legal_attached,
        legal_file_name=legal_file_name,
        legal_s3_key=legal_s3_key,
        db_session=db_session,
    )


def agent(question: str, session_id: str):

    llm = ChatOpenAI(
        verbose=True,
        model_name=settings.LLM_MODEL_NAME,
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        streaming=True,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant and your name is AdaletGPT. Make sure to use the rag_legal and rag_regulation tools for information.\n
                Use tavily_search_result_json tool if user's question is not related with case laws, statues and judicial precedents and decisions.\n
                You must answer in Turkish.
                If the question is unclear, require detailed question
                """,
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    tools = [
        rag_regulation_tool(),
        rag_legal_tool(),
        TavilySearchResults(max_results=1),
    ]

    agent = create_tool_calling_agent(llm, tools, prompt)

    """initialize session memory for agent"""
    chat_memory = init_postgres_chat_memory(session_id=session_id)
    memory = ConversationSummaryBufferMemory(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        memory_key="chat_history",
        return_messages=True,
        chat_memory=chat_memory,
        max_token_limit=3000,
        ai_prefix="Question",
        human_prefix="Answer",
    )

    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True, memory=memory
    )

    return agent_executor.invoke({"input": question})
