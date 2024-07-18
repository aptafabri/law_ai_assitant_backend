import asyncio
import json
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import ChatOpenAI
from core.config import settings
from tools.rag_regulation_tool import rag_regulation_tool
from tools.rag_legal_tool import rag_legal_tool
from langchain_core.prompts import ChatPromptTemplate
from core.prompt import main_agent_prompt
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.tools.tavily_search import TavilySearchResults
from crud.chat import init_postgres_chat_memory
from sqlalchemy.orm import Session
from typing import Any
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.agents import (
    AgentExecutor,
    create_tool_calling_agent,
)
from crud.chat import (
    summarize_session_streaming,
    init_postgres_chat_memory,
)
from crud.chat import (
    add_legal_session_summary,
    legal_session_exist,
)
from crud.rag import add_chat_history


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
                main_agent_prompt,
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
            output_key="output",
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
                print("--")

        if legal_session_exist(session_id=session_id, session=db_session) == False:
            # create the task which is running concurrently in background
            # without waiting until finish summarize streaming
            # summarize streaming and yield are excuting concurrently(in same time).
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

            # in this code, once finish the summarize streaming, then start yield data(time by time)

            # summary = ""
            # await summarize_session_streaming(
            #     question=question, answer=answer, llm=summary_streaming_llm
            # )
            # async for summary_token in summary_streaming_callback.aiter():
            #     summary += summary_token
            #     print("summary streaming:", summary)
            #     data_summary = json.dumps(
            #         {
            #             "message": {
            #                 "data_type": 1,
            #                 "content": summary,
            #             }
            #         }
            #     )
            #     yield data_summary

            await add_legal_session_summary(
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
        print("added chat history")

    except Exception as e:

        print(f"An error occurred: {e}")
