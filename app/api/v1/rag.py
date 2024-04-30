from fastapi import APIRouter, Depends, Body, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from crud.rag import rag_general_chat, rag_legal_chat, rag_test_chat , get_relevant_legal_cases
from crud.chat_general import add_message, summarize_session, add_session_summary, session_exist
from crud.chat_legal import add_legal_message, add_legal_session_summary, legal_session_exist, read_pdf
from crud.user import get_userid_by_token
from database.session import get_session
from schemas.message import ChatRequest, ChatAdd
from datetime import datetime
from core.auth_bearer import JWTBearer
router = APIRouter()

@router.post(
    "/chat",
    tags=["RagController"],
    status_code= 200
)
def chat_with_document(message:ChatRequest, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    response = rag_general_chat(question=message.question, session_id= message.session_id)
    #response = run_llm_conversational_retrievalchain_without_sourcelink(question=message.question, session_id= message.session_id)

    print("response", response)
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    user_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= message.question, role = "user", created_date=created_date)
    ai_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= response["answer"], role = "assistant", created_date= created_date)
    
    add_message(user_message, session)
    add_message(ai_message, session)
    
    print(session_exist(session_id=message.session_id, session= session))
    if(session_exist(session_id=message.session_id, session= session)==True):
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"],
            },
            status_code= 200
        )
    else:
        summary = summarize_session(question=message.question, answer= response["answer"])
        add_session_summary(user_id=user_id, session_id= message.session_id, summary= summary, session=session)
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"],
                "title":summary,
            },
            status_code= 200
        )

@router.post('/chat-legal', tags = ['RagController'], status_code = 200 )
def chat_with_legal(message:ChatRequest, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    response = rag_legal_chat(question=message.question, session_id= message.session_id)
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    user_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= message.question, role = "user", created_date=created_date)
    ai_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= response["answer"], role = "assistant", created_date= created_date)
    
    add_legal_message(user_message, session)
    add_legal_message(ai_message, session)
    
    print(legal_session_exist(session_id=message.session_id, session= session))
    if(legal_session_exist(session_id=message.session_id, session= session)==True):
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"],
            },
            status_code= 200
        )
    else:
        summary = summarize_session(question=message.question, answer= response["answer"])
        add_legal_session_summary(user_id=user_id, session_id= message.session_id, summary= summary, session=session)
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"],
                "title":summary,
            },
            status_code= 200
        )

@router.post('/get-legal-cases', tags= ['RagController'])
def  get_legal_cases(body:dict = Body(), dependencies=Depends(JWTBearer())):
    session_id = body["session_id"]
    legal_cases = get_relevant_legal_cases(session_id= session_id)
    return JSONResponse(
            content={
                "session_id": session_id,
                "legal_cases": legal_cases
            },
            status_code= 200
        )

@router.post("/chat-test")
async def rag_test(file:UploadFile = File(...)):
    pdf_contents = await file.read()
    extracted_text = read_pdf(pdf_contents)
    print(extracted_text)

    return {"ocr_text":extracted_text}
    # response = rag_test_chat(question=message.question, session_id= message.session_id)
    
    # return response
    






