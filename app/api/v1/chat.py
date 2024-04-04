from fastapi import APIRouter, Depends, Request, Body
from fastapi.responses import JSONResponse
from typing import  List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat import get_sessions_by_userid, get_messages_by_session_id, remove_messages_by_session_id, get_latest_messages_by_userid
from crud.user import get_userid_by_token
from schemas.message import SessionSummary, Message, SessionSummaryResponse, ChatHistoryResponse
from core.auth_bearer import JWTBearer
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from core.config import settings

router = APIRouter()

@router.post("/get-sessions-by-userid", tags= ["Chat Controller"], response_model= SessionSummaryResponse, status_code=200)
def get_sessions(access_token=Depends(JWTBearer()), session:Session = Depends(get_session)):
    user_id = get_userid_by_token(access_token)
    
    sessions = get_sessions_by_userid(user_id, session)
    print(sessions)
    return SessionSummaryResponse(sessions=sessions, access_token=access_token)

@router.post("/get-chathistory-by-sessionid", tags=['Chat Controller'], response_model=ChatHistoryResponse, status_code=200)
def get_chat_history(body:dict = Body(), access_token=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id =  get_userid_by_token(access_token)
    chat_history = get_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    return ChatHistoryResponse(chat_history=chat_history, access_token= access_token)

@router.post("/remove-session", tags=['Chat Controller'], status_code=200)
async def delete_session(body:dict = Body(), access_token=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id = get_userid_by_token(access_token)
    remove_info = remove_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    messages = PostgresChatMessageHistory(
        connection_string= settings.POSGRES_CHAT_HISTORY_URI,
        session_id = session_id
    )
    messages.clear()
    return JSONResponse(content= remove_info, status_code=200)

@router.post("/get-latest-session", tags=['Chat Controller'], response_model= ChatHistoryResponse, status_code=200)
def get_latest_session(access_token=Depends(JWTBearer()), session: Session = Depends(get_session)):
    user_id = get_userid_by_token(access_token)
    latest_session_chat_history = get_latest_messages_by_userid(user_id, session)
    
    return ChatHistoryResponse(chat_history=latest_session_chat_history, access_token= access_token)
