import asyncio
import json
from typing import Any

from sqlalchemy.orm import Session
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks import AsyncIteratorCallbackHandler

from core.config import settings
from core.prompt import main_agent_prompt
from crud.rag import add_chat_history
from crud.chat import (
    add_legal_session_summary,
    init_postgres_chat_memory,
    legal_session_exist,
    summarize_session_streaming,
)
from crud.user import calculate_llm_token
from log_config import configure_logging
from tools.rag_legal_tool import rag_legal_tool
from tools.rag_regulation_tool import rag_regulation_tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.callbacks import get_openai_callback  # Ensure this is from langchain, not langchain_community

# Configure logging
logger = configure_logging(__name__)

class QueueCallbackHandler(AsyncIteratorCallbackHandler):
    def on_llm_end(self, *args, **kwargs) -> Any:
        logger.info("Ended LLM streaming")
        self.done.set()

async def agent_run(
    standalone_question: str,
    question: str,
    user_id: int,
    session_id: str,
    legal_attached: bool,
    legal_s3_key: str,
    legal_file_name: str,
    db_session: Session,
):
    """
    Orchestrates the agent execution flow.

    Args:
        standalone_question (str): Processed user question.
        question (str): Original user question.
        user_id (int): Unique user identifier.
        session_id (str): Unique session identifier.
        legal_attached (bool): Indicates if a legal document is attached.
        legal_s3_key (str): S3 key for the legal document.
        legal_file_name (str): Filename of the legal document.
        db_session (Session): Database session object.

    Yields:
        Any: JSON-formatted data to be sent to the user.
    """
    logger.info(f"Starting agent_run for user_id: {user_id}, session_id: {session_id}")
    
    try:
        # Initialize LLM with function calling support
        llm = ChatOpenAI(
            model_name=settings.LLM_MODEL_NAME,  # Ensure the model supports function calling
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True,
            model_kwargs={"user": str(user_id)},
        )
        logger.debug("Initialized ChatOpenAI with function calling support")

        # Initialize summary LLM
        summary_streaming_callback = QueueCallbackHandler()
        summary_streaming_llm = ChatOpenAI(
            streaming=True,
            callbacks=[summary_streaming_callback],
            temperature=0,
            max_tokens=3000,
            model_name="gpt-3.5-turbo",
            openai_api_key=settings.OPENAI_API_KEY,
            model_kwargs={"user": str(user_id)},
        )
        logger.debug("Initialized summary LLM")

        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", main_agent_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        logger.debug("Created prompt template")

        # Initialize tools
        tools = [
            rag_regulation_tool(),
            rag_legal_tool(),
            TavilySearchResults(max_results=1),
        ]
        logger.debug("Initialized tools")

        # Create agent with function calling support
        agent = create_openai_functions_agent(
            llm=llm,
            tools=tools,
            prompt=prompt,
        )
        logger.debug("Created agent with function calling support")

        # Initialize memory
        chat_memory = init_postgres_chat_memory(session_id=session_id)
        memory = ConversationSummaryBufferMemory(
            llm=ChatOpenAI(
                model_name=settings.QUESTION_MODEL_NAME,
                temperature=0,
                openai_api_key=settings.OPENAI_API_KEY,
                model_kwargs={"user": str(user_id)},
            ),
            memory_key="chat_history",
            return_messages=True,
            chat_memory=chat_memory,
            max_token_limit=3000,
            ai_prefix="Question",
            human_prefix="Answer",
            output_key="output",
        )
        logger.debug("Initialized conversation memory")

        # Create agent executor
        agent_executor = AgentExecutor(
            agent=agent, tools=tools, verbose=True, memory=memory
        )
        logger.debug("Created agent executor")

        # Execute agent and stream responses
        answer = ""
        logger.info("Starting agent execution")
        with get_openai_callback() as cb:
            async for event in agent_executor.astream_events(
                {"input": standalone_question}, version="v1"
            ):
                kind = event.get("event")
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        answer += content
                        data = json.dumps({
                            "message": {
                                "data_type": 0,
                                "content": answer,
                            }
                        })
                        yield data
                elif kind == "on_tool_start":
                    logger.info(f"Starting tool: {event['name']}")
                elif kind == "on_tool_end":
                    logger.info(f"Finished tool: {event['name']}")

            logger.info("Agent execution completed")
            logger.info(f"Final answer: {answer}")
            logger.info(f"Total Tokens: {cb.total_tokens}")
            logger.info(f"Total Cost (USD): ${cb.total_cost}")

            # Process session summary if needed
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
                    data_summary = json.dumps({
                        "message": {
                            "data_type": 1,
                            "content": summary,
                        }
                    })
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

            # Yield legal file data
            yield json.dumps({
                "message": {
                    "data_type": 2,
                    "content": legal_file_name,
                }
            })
            logger.debug(f"Yielded legal file data: {legal_file_name}")

            yield json.dumps({
                "message": {
                    "data_type": 3,
                    "content": legal_s3_key,
                }
            })
            logger.debug(f"Yielded legal S3 key data: {legal_s3_key}")

            # Update database
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

            await calculate_llm_token(
                user_id=user_id,
                db_session=db_session,
                total_llm_tokens=cb.total_tokens,
            )
            logger.info("LLM token usage calculated and updated")

    except Exception as e:
        logger.exception("An error occurred during agent execution.")
        error_data = json.dumps({
            "message": {
                "data_type": -1,
                "content": "An internal error occurred. Please try again later."
            }
        })
        yield error_data
