from fastapi import APIRouter, Depends, Request
from typing import Any, List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat import get_sessions_by_userid, get_messages_by_session_id
from crud.user import get_userid_by_token
from schemas.message import SessionSummary, Message
from core.auth_bearer import JWTBearer
from core.config import settings
import jwt
router = APIRouter()

@router.post("/get-sessions-by-userid", tags= ["Chat Controller"], response_model= List[SessionSummary], status_code=200)
async def get_sessions(dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    user_id = await get_userid_by_token(dependencies)
    
    sessions = get_sessions_by_userid(user_id, session)
    return sessions

@router.post("/get-chathistory-by-sessionid", tags=['Chat Controller'], response_model=List[Message], status_code=200)
async def get_chat_history(request:Request, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    body = await request.json()
    session_id = body["session_id"]
    user_id = await get_userid_by_token(dependencies)
    chat_history = get_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    return chat_history
   