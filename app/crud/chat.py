from models import ChatHistory
from database.session import get_session
from schemas.message import ChatAdd, SessionSummary, Message
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete
from typing import List

def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:
    
    query = f"""
        SELECT *
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY id) AS row_num
            FROM public.chat_history
            WHERE session_id IN (
                SELECT DISTINCT ON (session_id) session_id
                FROM public.chat_history
                WHERE user_id = {user_id}
            )
        ) AS subquery
        WHERE row_num <= 2 ORDER BY created_date DESC;
    """
    results =session.execute(text(query)).fetchall()
    session_summary_array : List[SessionSummary] = []
    prev_element = None
    for index, result in enumerate(results):
        if prev_element is not None:
            if(index%2==1): 
                session_summary = SessionSummary(
                    session_id=result[2],
                    name=prev_element[3],
                    summary=result[3]
                )
                
                session_summary_array.append(session_summary)
        prev_element = result
    
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
        
        session_messages = session.query(ChatHistory.id) \
            .filter(ChatHistory.session_id == session_id, ChatHistory.user_id == user_id) \
            .all()
        
        message_ids =  [msg_id for (msg_id,) in session_messages]
        
        session.query(ChatHistory)\
            .filter(ChatHistory.id.in_(message_ids))\
            .delete(synchronize_session=False)
        session.commit()
                        
        return {"message":"Delted session successfully."} 

    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []
