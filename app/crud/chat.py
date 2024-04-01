from models import ChatHistory
from database.session import get_session
from schemas.message import ChatAdd, SessionSummary, Message
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError
from typing import List

def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:
    
    session_ids= session.query(ChatHistory.session_id).filter(ChatHistory.user_id == user_id).distinct().all()
    session_summary_array : List[SessionSummary] = []

    for session_id, in session_ids[::-1]:
        session_messages = session.query(ChatHistory).\
            filter(ChatHistory.session_id == session_id).\
            order_by(ChatHistory.created_date.asc()).limit(2).all()
        
        for session_message in session_messages:
            if(session_message.role == 'Human'):
                session_name = session_message.content
            else:
                session_summary = session_message.content

        session_summary = SessionSummary(
                session_id=session_id,
                name=session_name,
                summary=session_summary
        )
        
        session_summary_array.append(session_summary)
    
    print(session_summary_array)
    return session_summary_array
        
def get_messages_by_session_id(user_id:int, session_id:str, session: Session)->List[Message]:
    
    try:
        session_messages = session.query(ChatHistory.content, ChatHistory.role) \
            .filter(ChatHistory.session_id == session_id, ChatHistory.user_id == user_id) \
            .order_by(ChatHistory.created_date.asc()).all()
        return session_messages
    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []


def add_message(message:ChatAdd, session:Session):
    
    try:
        new_message = ChatHistory(
            user_id=message.user_id,
            session_id=message.session_id,
            content=message.content,
            role=message.role,
            created_date=message.created_date
        )
        session.add(new_message)
        session.commit()
        session.refresh(new_message)
    except SQLAlchemyError as e:
        print("An error occurred while adding a message to the database:", str(e))
        session.rollback()

def remove_messages_by_session_id(user_id:int, session_id:str, session: Session)->List[Message]:
    
    try:
        session_messages = session.query(ChatHistory) \
            .filter(ChatHistory.session_id == session_id, ChatHistory.user_id == user_id) \
            .delete()
        return {"message":"Delted session successfully."} 

    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []
