from fastapi import APIRouter, Depends, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from time import sleep
import asyncio
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
from datetime import datetime
from core.auth_bearer import JWTBearer
from crud.agent import agent_run

router = APIRouter()


@router.post("/chat", tags=["RagController"], status_code=200)
async def rag_regulation_chat(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    if not file:
        standalone_question = question
        print("no file attahed!!!")
    else:
        pdf_contents = await file.read()
        attached_pdf = True
        file_name = file.filename
        print(file_name)
        time_stamp = created_date.timestamp()
        legal_s3_key = f"{time_stamp}_{file_name}"
        upload_legal_description(
            file_content=pdf_contents,
            user_id=user_id,
            session_id=session_id,
            legal_s3_key=legal_s3_key,
        )
        pdf_contents = read_pdf(pdf_contents)
        standalone_question = generate_question(
            pdf_contents=pdf_contents, question=question
        )
    response = rag_chat(question=standalone_question, session_id=session_id)
    answer = response["answer"]
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
    add_legal_chat_message(ai_message, session)
    if legal_session_exist(session_id=session_id, session=session) == True:
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
        summary = summarize_session(question=standalone_question, answer=answer)
        add_legal_session_summary(
            user_id=user_id, session_id=session_id, summary=summary, session=session
        )
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


@router.post("/chat-streaming", tags=["RagController"], status_code=200)
async def rag_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    if not file:
        standalone_question = question
        print("no file attahed!!!")
    else:
        pdf_contents = await file.read()
        attached_pdf = True
        file_name = file.filename
        print(file_name)
        time_stamp = created_date.timestamp()
        legal_s3_key = f"{time_stamp}_{file_name}"
        upload_legal_description(
            file_content=pdf_contents,
            user_id=user_id,
            session_id=session_id,
            legal_s3_key=legal_s3_key,
        )
        pdf_contents = read_pdf(pdf_contents)
        standalone_question = generate_question(
            pdf_contents=pdf_contents, question=question
        )
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


@router.post("/get-legal-cases", tags=["RagController"])
def get_legal_cases(body: dict = Body(), dependencies=Depends(JWTBearer())):
    session_id = body["session_id"]
    legal_cases = get_relevant_legal_cases(session_id=session_id)
    return JSONResponse(
        content={"session_id": session_id, "legal_cases": legal_cases}, status_code=200
    )


@router.post("/chat-agent-streaming", tags=["RagController"], status_code=200)
async def rag_agent_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    if not file:
        standalone_question = question
        print("no file attahed!!!")
    else:
        pdf_contents = await file.read()
        attached_pdf = True
        file_name = file.filename
        print(file_name)
        time_stamp = created_date.timestamp()
        legal_s3_key = f"{time_stamp}_{file_name}"
        upload_legal_description(
            file_content=pdf_contents,
            user_id=user_id,
            session_id=session_id,
            legal_s3_key=legal_s3_key,
        )
        pdf_contents = read_pdf(pdf_contents)
        standalone_question = generate_question(
            pdf_contents=pdf_contents, question=question
        )

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
