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
from core import settings
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain_community.callbacks import get_openai_callback
from langchain.agents import (
    AgentExecutor,
    create_tool_calling_agent,
)
from crud.user import calculate_llm_token
from crud.chat import (
    summarize_session_streaming,
    init_postgres_chat_memory,
)
from crud.chat import (
    add_legal_session_summary,
    legal_session_exist,
)
from crud.rag import add_chat_history

from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)


class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        logger.info("Ended LLM streaming")
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
    logger.info(f"Starting agent_run for user_id: {user_id}, session_id: {session_id}")
    logger.debug(f"Standalone question: {standalone_question}")
    logger.debug(f"Question: {question}")
    logger.debug(f"Legal attached: {legal_attached}")
    logger.debug(f"Legal S3 key: {legal_s3_key}")
    logger.debug(f"Legal file name: {legal_file_name}")

    llm = ChatOpenAI(
        verbose=True,
        model_name=settings.LLM_MODEL_NAME,
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
        streaming=True,
        model_kwargs={"user": f"{user_id}"},
    )
    logger.debug("Initialized ChatOpenAI llm")

    summary_streaming_callback = QueueCallbackHandler()
    summary_streaming_llm = ChatOpenAI(
        streaming=True,
        callbacks=[summary_streaming_callback],
        temperature=0,
        max_tokens=3000,
        model_name=settings.LLM_MODEL_NAME,
        model_kwargs={"user": f"{user_id}"},
    )
    logger.debug("Initialized summary_streaming_llm")

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
    logger.debug("Created ChatPromptTemplate for agent")

    try:
        logger.debug("Initializing tools for agent")
        tools = [
            rag_regulation_tool(),
            rag_legal_tool(),
            TavilySearchResults(max_results=1),
        ]

        agent = create_tool_calling_agent(llm, tools, prompt)
        logger.debug("Agent created with create_tool_calling_agent")

        logger.debug("Initializing session memory for agent")
        chat_memory = init_postgres_chat_memory(session_id=session_id)
        memory = ConversationSummaryBufferMemory(
            llm=ChatOpenAI(
                model_name=settings.QUESTION_MODEL_NAME,
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
        logger.debug("ConversationSummaryBufferMemory initialized")

        agent_executor = AgentExecutor(
            agent=agent, tools=tools, verbose=True, memory=memory
        )
        logger.debug("AgentExecutor initialized")

        answer = ""
        logger.info("Starting agent execution")
        with get_openai_callback() as cb:
            logger.info("Processing agent events")
            async for event in agent_executor.astream_events(
                {"input": standalone_question}, version="v1"
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
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
                    logger.debug("--")
                    logger.info(
                        f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}"
                    )
                elif kind == "on_tool_end":
                    logger.info(f"Finished tool: {event['name']}")
                    logger.debug("--")

            # After streaming is complete, log the final answer
            logger.info(f"Final answer: {answer}")

            if not legal_session_exist(session_id=session_id, session=db_session):
                logger.info(f"Session {session_id} does not exist. Generating summary.")
                summary_task = asyncio.create_task(
                    summarize_session_streaming(
                        question=question, answer=answer, llm=summary_streaming_llm
                    )
                )
                summary = ""

                async for summary_token in summary_streaming_callback.aiter():
                    summary += summary_token
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
                logger.info(f"Final summary: {summary}")

                await add_legal_session_summary(
                    user_id=user_id,
                    session_id=session_id,
                    summary=summary,
                    session=db_session,
                )
                logger.info(f"Added legal session summary for session_id: {session_id}")

            legal_file_data = json.dumps(
                {
                    "message": {
                        "data_type": 2,
                        "content": legal_file_name,
                    }
                }
            )

            yield legal_file_data
            logger.debug(f"Yielded legal file data: {legal_file_name}")

            s3_key_data = json.dumps(
                {
                    "message": {
                        "data_type": 3,
                        "content": legal_s3_key,
                    }
                }
            )

            yield s3_key_data
            logger.debug(f"Yielded legal S3 key data: {legal_s3_key}")

        logger.info("Agent execution completed")
        logger.info(f"Total Tokens: {cb.total_tokens}")
        logger.info(f"Total Cost (USD): ${cb.total_cost}")
        total_llm_tokens = cb.total_tokens

        logger.debug("Adding chat history")
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
        logger.info("Chat history added successfully")

        logger.debug("Calculating LLM token usage")
        await calculate_llm_token(
            user_id=user_id,
            db_session=db_session,
            total_llm_tokens=total_llm_tokens
        )
        logger.info("LLM token usage calculated and updated")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
