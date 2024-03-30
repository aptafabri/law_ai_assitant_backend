from fastapi import APIRouter, Depends, Request
from typing import Any, List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat import get_sessions_by_userid, get_messages_by_session_id
from schemas.message import SessionSummary, Message
router = APIRouter()

@router.post("/get-sessions-by-userid", tags= ["Chat Controller"], response_model= List[SessionSummary])
async def get_sessions(request:Request, session:Session = Depends(get_session)):
    body = await request.json()
    print(body)
    sessions = get_sessions_by_userid(body["user_id"], session)
    
    return sessions

@router.post("/get-chathistory-by-sessionid", tags=['Chat Controller'], response_model=List[Message])
async def get_chat_history(request:Request, session: Session = Depends(get_session)):
    body = await request.json()
    session_id = body["session_id"]
    print(session_id)
    chat_history = get_messages_by_session_id(session_id=session_id, session=session)
    
    return chat_history
   