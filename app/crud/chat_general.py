from models import ChatHistory
from schemas.message import ChatAdd, SessionSummary, Message
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from langchain_openai import ChatOpenAI
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from models.session_summary import SessionsummaryTable
from datetime import datetime
from langchain_postgres import PostgresChatMessageHistory
import psycopg
from core.config import settings

 

def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:
    
    session_summary_array : List[SessionSummary] = []
    results = session.query(SessionsummaryTable)\
        .filter(SessionsummaryTable.user_id == user_id)\
        .order_by(SessionsummaryTable.favourite_date.desc()).all()
    session_summary_array = results
    return session_summary_array

                 
def get_messages_by_session_id(user_id:int, session_id:str, session: Session)->List[Message]:
    
    try:
        results = session.query(ChatHistory.content, ChatHistory.role) \
            .filter(ChatHistory.session_id == session_id, ChatHistory.user_id == user_id) \
            .order_by(ChatHistory.created_date.asc()).order_by(ChatHistory.id.asc()).all()
        
        message_array :List[Message] = []
        for result in results:
            message = Message(content=result[0], role=result[1])
            message_array.append(message)
            
        return message_array
    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []

def get_latest_messages_by_userid(user_id:int, session: Session)->List[Message]:
    try:
        
        latest_session_record_subquery = session.query(SessionsummaryTable.session_id, SessionsummaryTable.favourite_date)\
        .filter(SessionsummaryTable.user_id == user_id)\
        .order_by(SessionsummaryTable.favourite_date.desc())\
        .subquery()

        latest_session_record = session.query(
            latest_session_record_subquery.c.session_id,
            latest_session_record_subquery.c.favourite_date
        ).first()
        
        if latest_session_record:
            session_id = latest_session_record[0]
            session_messages = get_messages_by_session_id(user_id=user_id, session_id=session_id, session=session)
            return session_messages
        else:
            return []
    except SQLAlchemyError as e:
        # Handle SQLAlchemy errors
        print(f"SQLAlchemy error occurred: {e}")
        return []
    except Exception as e:
        # Handle other exceptions
        print(f"An error occurred: {e}")
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

def summarize_session( question:str, answer:str):
    llm = ChatOpenAI(temperature=0.5, model_name="gpt-4-1106-preview")
    # Define prompt
    prompt_template = """
        I want you to make concise summary using following conversation.
        You must write concise summary as title format with a 5-8 in turkish
        CONVERSATION:
        ============
        Human:{question}
        AI:{answer}
        ============
        CONCISE Summary:
    """
    prompt = PromptTemplate.from_template(prompt_template)

    # Define LLM chain
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    response = llm_chain.invoke({
        "question":question,
        "answer":answer
    })

    return response['text']

def add_session_summary(session_id: str, user_id: int,summary:str, session:Session):
    
    
    chat_session_db = SessionsummaryTable(user_id=user_id,session_id =session_id, summary= summary)
    session.add(chat_session_db)
    session.commit()
    session.refresh(chat_session_db)
    
    return {
        "session_id":session_id,
        "summary": summary
    }

def remove_session_summary(session_id:str, session:Session):
    
    existing_session_summary = session.query(SessionsummaryTable)\
        .filter(SessionsummaryTable.session_id == session_id)\
        .delete()
    session.commit()

def session_exist(session_id:str, session: Session):
    existing_session = session.query(SessionsummaryTable)\
        .filter(SessionsummaryTable.session_id == session_id).first()
    print("existing session:", existing_session)
    if existing_session:
        return True
    else :
        return False

def upvote_chat_session(session_id:str, user_id:int, session:Session):
    try:
        update_session = session.query(SessionsummaryTable)\
            .filter(SessionsummaryTable.session_id == session_id, SessionsummaryTable.user_id == user_id).first()

        update_session.is_favourite = True
        update_session.favourite_date =  datetime.now()

        session.commit()

        return {"success": True}
    
    except SQLAlchemyError as e:

        return {"success": False}

def devote_chat_session(session_id:str, user_id:int, session:Session):
    try:
        update_session = session.query(SessionsummaryTable)\
            .filter(SessionsummaryTable.session_id == session_id, SessionsummaryTable.user_id == user_id).first()

        update_session.is_favourite = False
        update_session.favourite_date =  update_session.created_date

        session.commit()

        return {"success": True}
    
    except SQLAlchemyError as e:

        return {"success": False} 

def init_postgres_chat_memory(session_id:str):
    table_name='message_store'
    sync_connection = psycopg.connect(settings.POSTGRES_CHAT_HISTORY_URI)
    PostgresChatMessageHistory.create_tables(sync_connection, table_name)
    chat_memory=PostgresChatMessageHistory(
            table_name,
            session_id,
            sync_connection = sync_connection
    )

    return chat_memory
def init_postgres_legal_chat_memory(session_id:str):
    table_name='legal_message_store'
    sync_connection = psycopg.connect(settings.POSTGRES_CHAT_HISTORY_URI)
    PostgresChatMessageHistory.create_tables(sync_connection, table_name)
    chat_memory=PostgresChatMessageHistory(
            table_name,
            session_id,
            sync_connection = sync_connection
    )

    return chat_memory




    
    