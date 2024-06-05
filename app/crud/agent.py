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
    create_openai_tools_agent,
)
from crud.chat_general import (
    add_message,
    summarize_session_streaming,
    add_session_summary,
    session_exist,
    init_postgres_chat_memory,
)
from crud.chat_legal import (
    add_legal_session_summary,
    legal_session_exist,
)
from crud.rag import add_legal_chat_history


class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        print("ended streaming")
        return self.done.set()


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
        model_kwargs={"user": f"{user_id}"},
    )

    summary_streaming_callback = QueueCallbackHandler()
    summary_streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[summary_streaming_callback],
        temperature=0,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
        model_kwargs={"user": f"{user_id}"},
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """ You are an AI assistant specialized in Turkish Law, and your name is AdaletGPT.\n
                    Your purpose is to answer about law.\n
                    You can use the rag_legal, rag_regulation, and tavily_search_result_json tools.\n
                    Use the tavily_search_result_json tool if the question is not related to law such as case laws, statutes, and judicial precedents and decisions and so on.
                    You must answer in Turkish, and your answer must be based on the tools.\n
                    Don't use tools to answer unless you NEED to.\n
                    Don't mention about tools in answer.\n
                    You must use one tool for each question.\n
                    If the question is unclear, ask for more details.\n
                    If you don't know, just say "I don't know" and don't try to make answer.\n
                    If you find the answer, write it in detail and you must include a list of sources that are directly used to derive the final answer.
                    Do NOT process source file names and use  as is.
                    Do not include source file names that are irrelevant to the final answer.\n""",
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    try:
        tools = [
            rag_regulation_tool(),
            rag_legal_tool(),
            TavilySearchResults(max_results=1),
        ]

        agent = create_tool_calling_agent(llm, tools, prompt)

        """initialize session memory for agent"""
        chat_memory = init_postgres_chat_memory(session_id=session_id)
        memory = ConversationSummaryBufferMemory(
            llm=ChatOpenAI(
                model_name="gpt-4-1106-preview",
                temperature=0,
                model_kwargs={"user": f"{user_id}"},
            ),
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
                    print("streaming_answer:", answer)
                    answer += content
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
                user_id=user_id,
                session_id=session_id,
                summary=summary,
                session=db_session,
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

        add_legal_chat_history(
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=answer,
            legal_attached=legal_attached,
            legal_file_name=legal_file_name,
            legal_s3_key=legal_s3_key,
            db_session=db_session,
        )
        print("added chat history")

    except Exception as e:

        print(f"An error occurred: {e}")
