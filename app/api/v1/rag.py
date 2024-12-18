from fastapi import APIRouter, Depends, Body, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from datetime import datetime
from log_config import configure_logging

from crud.rag import (
    rag_chat,
    rag_streaming_chat,
    get_relevant_legal_cases,
)

from crud.chat import (
    add_legal_chat_message,
    add_legal_session_summary,
    legal_session_exist,
    read_pdf,
    upload_legal_description,
    generate_question,
    summarize_session,
    init_postgres_chat_memory,
)
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
from crud.user import get_userid_by_token
from database.session import get_session
from schemas.message import LegalChatAdd
from core.auth_bearer import JWTBearer
from crud.agent import agent_run

# Configure logging
logger = configure_logging(__name__)

router = APIRouter()


@router.post("/chat", tags=["RagController"], status_code=200)
async def rag_regulation_chat(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    logger.info(f"Received /chat request with session_id: {session_id}, question: {question}")
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    try:
        user_id = get_userid_by_token(dependencies)
        created_date = datetime.now()
        if not file:
            standalone_question = question
            logger.debug("No file attached in the request.")
        else:
            logger.info(f"File attached: {file.filename}")
            pdf_contents = await file.read()
            attached_pdf = True
            file_name = file.filename
            logger.debug(f"File name: {file_name}")
            time_stamp = created_date.timestamp()
            legal_s3_key = f"{time_stamp}_{file_name}"
            upload_legal_description(
                file_content=pdf_contents,
                user_id=user_id,
                session_id=session_id,
                legal_s3_key=legal_s3_key,
            )
            logger.debug(f"Uploaded legal description with s3 key: {legal_s3_key}")
            pdf_contents = read_pdf(pdf_contents)
            logger.debug("Read PDF contents.")
            standalone_question = generate_question(
                pdf_contents=pdf_contents, question=question
            )
            logger.debug("Generated standalone question.")
        response = rag_chat(question=standalone_question, session_id=session_id)
        answer = response["answer"]
        logger.debug("Received answer from rag_chat.")
        user_message = LegalChatAdd(
            user_id=user_id,
            session_id=session_id,
            content=question,
            role="user",
            legal_attached=attached_pdf,
            legal_file_name=file_name,
            legal_s3_key=legal_s3_key,
            created_date=created_date,
        )
        ai_message = LegalChatAdd(
            user_id=user_id,
            session_id=session_id,
            content=answer,
            role="assistant",
            legal_attached=False,
            legal_file_name="",
            legal_s3_key="",
            created_date=created_date,
        )
        add_legal_chat_message(user_message, session)
        logger.debug("Added user message to chat.")
        add_legal_chat_message(ai_message, session)
        logger.debug("Added AI message to chat.")
        if legal_session_exist(session_id=session_id, session=session):
            logger.info(f"Legal session exists for session_id: {session_id}")
            return JSONResponse(
                content={
                    "user_id": user_id,
                    "session_id": session_id,
                    "question": question,
                    "legal_attached": attached_pdf,
                    "legal_file_name": file_name,
                    "legal_s3_key": legal_s3_key,
                    "answer": answer,
                },
                status_code=200,
            )
        else:
            logger.info(f"Legal session does not exist for session_id: {session_id}. Summarizing session.")
            summary = summarize_session(question=standalone_question, answer=answer)
            add_legal_session_summary(
                user_id=user_id, session_id=session_id, summary=summary, session=session
            )
            logger.debug("Added legal session summary.")
            return JSONResponse(
                content={
                    "user_id": user_id,
                    "session_id": session_id,
                    "question": question,
                    "legal_attached": attached_pdf,
                    "legal_file_name": file_name,
                    "legal_s3_key": legal_s3_key,
                    "answer": answer,
                    "title": summary,
                },
                status_code=200,
            )
    except Exception as e:
        logger.exception(f"An error occurred in /chat endpoint: {e}")
        return JSONResponse(
            content={"error": "An internal error occurred."},
            status_code=500,
        )


@router.post("/chat-streaming", tags=["RagController"], status_code=200)
async def rag_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    logger.info(f"Received /chat-streaming request with session_id: {session_id}, question: {question}")
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    try:
        user_id = get_userid_by_token(dependencies)
        created_date = datetime.now()
        if not file:
            standalone_question = question
            logger.debug("No file attached in the request.")
        else:
            logger.info(f"File attached: {file.filename}")
            pdf_contents = await file.read()
            attached_pdf = True
            file_name = file.filename
            logger.debug(f"File name: {file_name}")
            time_stamp = created_date.timestamp()
            legal_s3_key = f"{time_stamp}_{file_name}"
            upload_legal_description(
                file_content=pdf_contents,
                user_id=user_id,
                session_id=session_id,
                legal_s3_key=legal_s3_key,
            )
            logger.debug(f"Uploaded legal description with s3 key: {legal_s3_key}")
            pdf_contents = read_pdf(pdf_contents)
            logger.debug("Read PDF contents.")
            standalone_question = generate_question(
                pdf_contents=pdf_contents, question=question
            )
            logger.debug("Generated standalone question.")
        chat_memory = init_postgres_chat_memory(session_id=session_id)
        memory = ConversationSummaryBufferMemory(
            llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
            memory_key="chat_history",
            return_messages="on",
            chat_memory=chat_memory,
            max_token_limit=3000,
            output_key="answer",
            ai_prefix="Question",
            human_prefix="Answer",
        )
        logger.debug("Initialized conversation memory.")
        return EventSourceResponse(
            rag_streaming_chat(
                standalone_question=standalone_question,
                question=question,
                session_id=session_id,
                user_id=user_id,
                db_session=session,
                chat_history=memory.buffer,
                legal_attached=attached_pdf,
                legal_file_name=file_name,
                legal_s3_key=legal_s3_key,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"An error occurred in /chat-streaming endpoint: {e}")
        return JSONResponse(
            content={"error": "An internal error occurred."},
            status_code=500,
        )


@router.post("/get-legal-cases", tags=["RagController"])
def get_legal_cases(body: dict = Body(), dependencies=Depends(JWTBearer())):
    logger.info("Received /get-legal-cases request.")
    try:
        session_id = body["session_id"]
        logger.debug(f"Session ID: {session_id}")
        legal_cases = get_relevant_legal_cases(session_id=session_id)
        logger.debug(f"Retrieved legal cases: {legal_cases}")
        return JSONResponse(
            content={"session_id": session_id, "legal_cases": legal_cases}, status_code=200
        )
    except Exception as e:
        logger.exception(f"An error occurred in /get-legal-cases endpoint: {e}")
        return JSONResponse(
            content={"error": "An internal error occurred."},
            status_code=500,
        )


@router.post("/chat-agent-streaming", tags=["RagController"], status_code=200)
async def rag_agent_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    logger.info(f"Received /chat-agent-streaming request with session_id: {session_id}, question: {question}")
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    try:
        user_id = get_userid_by_token(dependencies)
        created_date = datetime.now()
        if file is None:
            standalone_question = question
            logger.debug("No file attached in the request.")
        else:
            if file.size > 500*1024:
                return JSONResponse(status_code=413, content="The File is too large. Please attach the file which is smaller than 500KB.")
            else:
                logger.info(f"File attached: {file.filename}")
                pdf_contents = await file.read()
                attached_pdf = True
                file_name = file.filename
                logger.debug(f"File name: {file_name}")
                time_stamp = created_date.timestamp()
                legal_s3_key = f"{time_stamp}_{file_name}"
                upload_legal_description(
                    file_content=pdf_contents,
                    user_id=user_id,
                    session_id=session_id,
                    legal_s3_key=legal_s3_key,
                )
                logger.debug(f"Uploaded legal description with s3 key: {legal_s3_key}")
                pdf_contents = read_pdf(pdf_contents)
                logger.debug("Read PDF contents.")
                standalone_question = generate_question(
                    pdf_contents=pdf_contents, question=question
                )
                logger.debug("Generated standalone question.")
                return EventSourceResponse(
                    agent_run(
                        standalone_question=standalone_question,
                        question=question,
                        session_id=session_id,
                        user_id=user_id,
                        db_session=session,
                        legal_attached=attached_pdf,
                        legal_file_name=file_name,
                        legal_s3_key=legal_s3_key,
                    ),
                    media_type="text/event-stream",
                )
    except Exception as ex:
        logger.exception(f"An error occurred in /chat-agent-streaming endpoint: {ex}")
        return JSONResponse(
            content={"error": f"An internal error occurred:{ex}"},
            status_code=500,
        )
