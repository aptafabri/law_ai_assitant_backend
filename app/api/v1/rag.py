from fastapi import APIRouter, Depends, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from time import sleep
import asyncio
from crud.rag import (
    rag_general_chat,
    rag_legal_chat,
    rag_general_streaming_chat,
    rag_legal_streaming_chat,
    get_relevant_legal_cases,
)
from crud.chat_general import (
    add_message,
    summarize_session,
    add_session_summary,
    session_exist,
    init_postgres_chat_memory,
)
from crud.chat_legal import (
    add_legal_chat_message,
    add_legal_session_summary,
    legal_session_exist,
    read_pdf,
    upload_legal_description,
    generate_question,
    init_postgres_legal_chat_memory,
)
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryBufferMemory
from crud.user import get_userid_by_token
from database.session import get_session
from schemas.message import ChatRequest, ChatAdd, LegalChatAdd
from datetime import datetime
from core.auth_bearer import JWTBearer
from crud.agent import agent_run, agent

router = APIRouter()


@router.post("/chat", tags=["RagController"], status_code=200)
def rag_general(
    message: ChatRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    response = rag_general_chat(
        question=message.question, session_id=message.session_id
    )
    # response = run_llm_conversational_retrievalchain_without_sourcelink(question=message.question, session_id= message.session_id)

    print("response", type(response), response)

    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    user_message = ChatAdd(
        user_id=user_id,
        session_id=message.session_id,
        content=message.question,
        role="user",
        created_date=created_date,
    )
    ai_message = ChatAdd(
        user_id=user_id,
        session_id=message.session_id,
        content=response["answer"],
        role="assistant",
        created_date=created_date,
    )

    add_message(user_message, session)
    add_message(ai_message, session)

    print(session_exist(session_id=message.session_id, session=session))
    if session_exist(session_id=message.session_id, session=session) == True:
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question": message.question,
                "answer": response["answer"],
            },
            status_code=200,
        )
    else:
        summary = summarize_session(
            question=message.question, answer=response["answer"]
        )
        add_session_summary(
            user_id=user_id,
            session_id=message.session_id,
            summary=summary,
            session=session,
        )
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question": message.question,
                "answer": response["answer"],
                "title": summary,
            },
            status_code=200,
        )


@router.post("/chat-legal", tags=["RagController"], status_code=200)
async def rag_legal(
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
    response = rag_legal_chat(question=standalone_question, session_id=session_id)
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


@router.post("/get-legal-cases", tags=["RagController"])
def get_legal_cases(body: dict = Body(), dependencies=Depends(JWTBearer())):
    session_id = body["session_id"]
    legal_cases = get_relevant_legal_cases(session_id=session_id)
    return JSONResponse(
        content={"session_id": session_id, "legal_cases": legal_cases}, status_code=200
    )


@router.post("/chat-streaming", tags=["RagController"], status_code=200)
async def rag_general_streaming(
    message: ChatRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
) -> EventSourceResponse:

    chat_memory = init_postgres_chat_memory(session_id=message.session_id)
    memory = ConversationSummaryBufferMemory(
        llm=ChatOpenAI(model_name="gpt-4-1106-preview", temperature=0),
        memory_key="chat_history",
        return_messages=True,
        chat_memory=chat_memory,
        max_token_limit=3000,
        output_key="answer",
        ai_prefix="Question",
        human_prefix="Answer",
    )
    user_id = get_userid_by_token(dependencies)

    return EventSourceResponse(
        rag_general_streaming_chat(
            user_id=user_id,
            question=message.question,
            session_id=message.session_id,
            chat_history=memory.buffer,
            db_session=session,
        ),
        media_type="text/event-stream",
    )


@router.post("/chat-legal-streaming", tags=["RagController"], status_code=200)
async def rag_legal_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
) -> EventSourceResponse:
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
    chat_memory = init_postgres_legal_chat_memory(session_id=session_id)
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
        rag_legal_streaming_chat(
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


@router.post("/chat-agent-streaming", tags=["RagController"], status_code=200)
async def rag_agent_streaming(
    session_id: str = Form(),
    question: str = Form(),
    file: UploadFile = File(None),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
) -> EventSourceResponse:
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
        if pdf_contents == "":
            standalone_question = question
        else:
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


@router.post("/chat-agent", tags=["RagController"], status_code=200)
async def rag_agent(
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
    response = agent(question=standalone_question, session_id=session_id)
    
    answer = response["output"]
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
