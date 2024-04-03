from fastapi import APIRouter, Depends, Request, Body
from fastapi.responses import JSONResponse
from typing import  List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat import get_sessions_by_userid, get_messages_by_session_id, remove_messages_by_session_id, get_latest_messages_by_userid
from crud.user import get_userid_by_token
from schemas.message import SessionSummary, Message
from core.auth_bearer import JWTBearer
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from core.config import settings

router = APIRouter()

@router.post("/get-sessions-by-userid", tags= ["Chat Controller"], response_model= List[SessionSummary], status_code=200)
async def get_sessions(dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    user_id = get_userid_by_token(dependencies)
    
    sessions = await get_sessions_by_userid(user_id, session)
    return sessions

@router.post("/get-chathistory-by-sessionid", tags=['Chat Controller'], response_model=List[Message], status_code=200)
async def get_chat_history(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id =  get_userid_by_token(dependencies)
    chat_history = await get_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    return chat_history

@router.post("/remove-session", tags=['Chat Controller'], status_code=200)
async def delete_session(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    remove_info = await remove_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    messages = PostgresChatMessageHistory(
        connection_string= settings.POSGRES_CHAT_HISTORY_URI,
        session_id = session_id
    )
    messages.clear()
    return JSONResponse(content= remove_info, status_code=200)

@router.post("/get-latest-session", tags=['Chat Controller'], response_model=List[Message], status_code=200)
def get_latest_session(dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    user_id = get_userid_by_token(dependencies)
    latest_session_messages = get_latest_messages_by_userid(user_id, session)
    
    return latest_session_messages