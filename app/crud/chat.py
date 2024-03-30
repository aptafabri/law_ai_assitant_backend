from models import ChatHistory
from database.session import get_session
from schemas.message import ChatAdd, SessionSummary, Message
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List

def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:
    
    # Get subquery to get distinct session ids
    subquery = session.query(ChatHistory.session_id, func.max(ChatHistory.created_date).label('latest_date'))\
                  .filter(ChatHistory.user_id == user_id)\
                  .group_by(ChatHistory.session_id)\
                  .subquery()

    # Outer query to select distinct session_id values ordered by latest_date
    session_ids = session.query(subquery.c.session_id).order_by(subquery.c.latest_date.desc())
    session_summary_array : List[SessionSummary] = []

    for session_id, in session_ids:
        session_messages = session.query(ChatHistory).\
            filter(ChatHistory.session_id == session_id).\
            order_by(ChatHistory.created_date.asc()).limit(2).all()
        
        if len(session_messages) == 2:
            # Create a session summary if there are exactly two messages
            session_summary = SessionSummary(
                session_id=session_id,
                name=session_messages[0].content,
                summary=session_messages[1].content
            )
            session_summary_array.append(session_summary)
        elif len(session_messages) == 1:
            # Handle cases where there's only one message for the session
            session_summary = SessionSummary(
                session_id=session_id,
                name=session_messages[0].content,
                summary=None
            )
            session_summary_array.append(session_summary)
        else:
            # Handle cases where there are no messages for the session
            session_summary = SessionSummary(
                session_id=session_id,
                name=None,
                summary=None
            )
            session_summary_array.append(session_summary)
    return session_summary_array
        
def get_messages_by_session_id(session_id:str, session: Session)->List[Message]:
    
    session_messages = session.query(ChatHistory.id, ChatHistory.content, ChatHistory.role, ChatHistory.created_date)\
        .filter(ChatHistory.session_id == session_id)\
        .order_by(ChatHistory.created_date.asc()).all()
    
    return session_messages

def add_message(message:ChatAdd, session:Session):
    
    new_message = ChatHistory(
        user_id=message.user_id,
        session_id=message.session_id,
        content=message.content,
        role = message.role,
        created_date = message.created_date 
    )
    session.add(new_message)
    session.commit()
    session.refresh(new_message)


    