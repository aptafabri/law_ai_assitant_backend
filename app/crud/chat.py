import os
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from langchain_openai import ChatOpenAI
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from models.session_summary_legal import LegalSessionSummary
from models import LegalChatHistory
from datetime import datetime
from langchain_postgres import PostgresChatMessageHistory
import psycopg
from core.config import settings
import boto3
import pytesseract as tess
from PIL import Image
from pdf2image import convert_from_bytes
from schemas.message import (
    ChatAdd,
    SessionSummary,
    LegalMessage,
    LegalChatAdd,
    SharedSessionSummary,
    ArchivedSessionSummary,
)
from core.config import settings
from core.prompt import (
    summary_legal_session_prompt_template,
    summary_session_prompt_template,
)
from langsmith import traceable
import uuid
from datetime import datetime
import asyncio

from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)

# tess.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tess.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"

s3_client = boto3.client(
    service_name="s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
)

def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:
    logger.info(f"Retrieving sessions for user_id: {user_id}")
    try:
        results = (
            session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.is_archived == False,
            )
            .order_by(LegalSessionSummary.favourite_date.desc())
            .all()
        )
        logger.debug(f"Found {len(results)} sessions for user_id: {user_id}")
        return results
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemyError occurred: {e}")
        return []

def get_messages_by_session_id(
    user_id: int, session_id: str, session: Session
) -> List[LegalMessage]:
    logger.info(f"Retrieving messages for user_id: {user_id}, session_id: {session_id}")
    try:
        results = (
            session.query(
                LegalChatHistory.content,
                LegalChatHistory.role,
                LegalChatHistory.legal_attached,
                LegalChatHistory.legal_file_name,
                LegalChatHistory.legal_s3_key,
            )
            .filter(
                LegalChatHistory.session_id == session_id,
                LegalChatHistory.user_id == user_id,
            )
            .order_by(LegalChatHistory.created_date.asc())
            .order_by(LegalChatHistory.id.asc())
            .all()
        )

        message_array: List[LegalMessage] = []
        for result in results:
            message = LegalMessage(
                content=result[0],
                role=result[1],
                legal_attached=result[2],
                legal_file_name=result[3],
                legal_s3_key=result[4],
            )
            message_array.append(message)
        logger.debug(f"Retrieved {len(message_array)} messages for session_id: {session_id}")
        return message_array
    except SQLAlchemyError as e:
        logger.error(f"An error occurred while querying the database: {e}")
        return []

def get_latest_messages_by_userid(user_id: int, session: Session) -> List[LegalMessage]:
    logger.info(f"Retrieving latest messages for user_id: {user_id}")
    try:
        latest_session_record_subquery = (
            session.query(
                LegalSessionSummary.session_id, LegalSessionSummary.favourite_date
            )
            .filter(LegalSessionSummary.user_id == user_id)
            .order_by(LegalSessionSummary.favourite_date.desc())
            .subquery()
        )

        latest_session_record = session.query(
            latest_session_record_subquery.c.session_id,
            latest_session_record_subquery.c.favourite_date,
        ).first()

        if latest_session_record:
            session_id = latest_session_record[0]
            session_messages = get_messages_by_session_id(
                user_id=user_id, session_id=session_id, session=session
            )
            logger.debug(f"Retrieved latest messages for session_id: {session_id}")
            return session_messages
        else:
            logger.info(f"No sessions found for user_id: {user_id}")
            return []
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error occurred: {e}")
        return []
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return []

def add_legal_message(message: ChatAdd, session: Session):
    logger.info(f"Adding legal message for user_id: {message.user_id}, session_id: {message.session_id}")
    try:
        new_message = LegalChatHistory(
            user_id=message.user_id,
            session_id=message.session_id,
            content=message.content,
            role=message.role,
            created_date=message.created_date,
        )
        session.add(new_message)
        session.commit()
        session.refresh(new_message)
        logger.debug("Legal message added successfully")
    except SQLAlchemyError as e:
        logger.error(f"An error occurred while adding a message to the database: {e}")
        session.rollback()

def add_legal_chat_message(message: LegalChatAdd, session: Session):
    logger.info(f"Adding legal chat message for user_id: {message.user_id}, session_id: {message.session_id}")
    try:
        new_message = LegalChatHistory(
            user_id=message.user_id,
            session_id=message.session_id,
            content=message.content,
            role=message.role,
            legal_attached=message.legal_attached,
            legal_file_name=message.legal_file_name,
            legal_s3_key=message.legal_s3_key,
            created_date=message.created_date,
        )
        session.add(new_message)
        session.commit()
        session.refresh(new_message)
        logger.debug("Legal chat message added successfully")
    except SQLAlchemyError as e:
        logger.error(f"An error occurred while adding a message to the database: {e}")
        session.rollback()

def remove_messages_by_session_id(user_id: int, session_id: str, session: Session):
    logger.info(f"Removing messages for user_id: {user_id}, session_id: {session_id}")
    try:
        session.query(LegalChatHistory).filter(
            LegalChatHistory.session_id == session_id,
            LegalChatHistory.user_id == user_id,
        ).delete(synchronize_session=False)
        session.commit()
        logger.debug(f"Messages deleted for session_id: {session_id}")
        return {"message": "Deleted session successfully."}
    except SQLAlchemyError as e:
        logger.error(f"An error occurred while querying the database: {e}")
        session.rollback()
        return {"message": "Failed to delete session."}

def summarize_session(question: str, answer: str):
    logger.info("Summarizing session")
    try:
        llm = ChatOpenAI(temperature=0.5, model_name="gpt-4-1106-preview")
        prompt_template = """
            I want you to make concise summary using following conversation.
            You must write concise summary as title format with a 5-8 words in turkish
            CONVERSATION:
            ============
            Human:{question}
            AI:{answer}
            ============
            CONCISE Summary:
        """
        prompt = PromptTemplate.from_template(prompt_template)
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        response = llm_chain.invoke({"question": question, "answer": answer})
        logger.debug(f"Session summary: {response['text']}")
        return response["text"]
    except Exception as e:
        logger.error(f"Error during session summarization: {e}")
        return ""

async def summarize_session_streaming(question: str, answer: str, llm):
    logger.info("Summarizing session with streaming")
    try:
        prompt = PromptTemplate.from_template(summary_session_prompt_template)
        llm_chain = prompt | llm | StrOutputParser()
        result = await llm_chain.ainvoke({"question": question, "answer": answer})
        logger.debug(f"Session summary (streaming): {result}")
        return result
    except Exception as e:
        logger.error(f"Error during streaming summarization: {e}")
        return ""

async def add_legal_session_summary(
    session_id: str, user_id: int, summary: str, session: Session
):
    logger.info(f"Adding legal session summary for user_id: {user_id}, session_id: {session_id}")
    try:
        chat_session_db = LegalSessionSummary(
            user_id=user_id, session_id=session_id, summary=summary
        )
        session.add(chat_session_db)
        session.commit()
        session.refresh(chat_session_db)
        logger.debug("Legal session summary added successfully")
        return {"session_id": session_id, "summary": summary}
    except SQLAlchemyError as e:
        logger.error(f"Error adding legal session summary: {e}")
        session.rollback()
        return {"message": "Failed to add session summary."}

def remove_session_summary(session_id: str, session: Session):
    logger.info(f"Removing session summary for session_id: {session_id}")
    try:
        session.query(LegalSessionSummary).filter(
            LegalSessionSummary.session_id == session_id
        ).delete()
        session.commit()
        logger.debug("Session summary removed successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error removing session summary: {e}")
        session.rollback()

def legal_session_exist(session_id: str, session: Session):
    logger.info(f"Checking if session exists for session_id: {session_id}")
    try:
        existing_session = (
            session.query(LegalSessionSummary)
            .filter(LegalSessionSummary.session_id == session_id)
            .first()
        )
        exists = existing_session is not None
        logger.debug(f"Session exists: {exists}")
        return exists
    except SQLAlchemyError as e:
        logger.error(f"Error checking session existence: {e}")
        return False

def upvote_chat_session(session_id: str, user_id: int, session: Session):
    logger.info(f"Upvoting chat session for user_id: {user_id}, session_id: {session_id}")
    try:
        update_session = (
            session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.user_id == user_id,
            )
            .first()
        )

        if update_session:
            update_session.is_favourite = True
            update_session.favourite_date = datetime.now()
            session.commit()
            logger.debug("Chat session upvoted successfully")
            return {"success": True}
        else:
            logger.warning("Chat session not found for upvoting")
            return {"success": False}
    except SQLAlchemyError as e:
        logger.error(f"Error upvoting chat session: {e}")
        session.rollback()
        return {"success": False}

def devote_chat_session(session_id: str, user_id: int, session: Session):
    logger.info(f"Devoting chat session for user_id: {user_id}, session_id: {session_id}")
    try:
        update_session = (
            session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.user_id == user_id,
            )
            .first()
        )

        if update_session:
            update_session.is_favourite = False
            update_session.favourite_date = update_session.created_date
            session.commit()
            logger.debug("Chat session devoted successfully")
            return {"success": True}
        else:
            logger.warning("Chat session not found for devoting")
            return {"success": False}
    except SQLAlchemyError as e:
        logger.error(f"Error devoting chat session: {e}")
        session.rollback()
        return {"success": False}

def init_postgres_chat_memory(session_id: str):
    logger.info(f"Initializing Postgres chat memory for session_id: {session_id}")
    try:
        table_name = "legal_message_store"
        sync_connection = psycopg.connect(settings.POSTGRES_CHAT_HISTORY_URI)
        PostgresChatMessageHistory.create_tables(sync_connection, table_name)
        chat_memory = PostgresChatMessageHistory(
            table_name, session_id, sync_connection=sync_connection
        )
        logger.debug("Postgres chat memory initialized successfully")
        return chat_memory
    except Exception as e:
        logger.error(f"Error initializing Postgres chat memory: {e}")
        return None

def upload_legal_description(file_content, user_id, session_id, legal_s3_key):
    logger.info(f"Uploading legal description for user_id: {user_id}, session_id: {session_id}")
    try:
        s3_key = f"{user_id}/{session_id}/{legal_s3_key}"
        s3_client.put_object(Bucket=settings.AWS_BUCKET_NAME, Body=file_content, Key=s3_key)
        logger.debug(f"Legal description uploaded to s3_key: {s3_key}")
    except Exception as e:
        logger.error(f"Error uploading legal description: {e}")

def download_legal_description(user_id, session_id, legal_s3_key):
    logger.info(f"Downloading legal description for user_id: {user_id}, session_id: {session_id}")
    try:
        s3_key = f"{user_id}/{session_id}/{legal_s3_key}"
        logger.debug(f"s3_key: {s3_key}")
        data = s3_client.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=s3_key)
        logger.debug("Legal description downloaded successfully")
        return data
    except Exception as e:
        logger.error(f"Error downloading legal description: {e}")
        return None

def delete_s3_bucket_folder(user_id, session_id):
    logger.info(f"Deleting S3 bucket folder for user_id: {user_id}, session_id: {session_id}")
    try:
        objects = s3_client.list_objects(
            Bucket=settings.AWS_BUCKET_NAME, Prefix=f"{user_id}/{session_id}"
        )
        if objects.get("Contents") is not None:
            for o in objects.get("Contents"):
                s3_client.delete_object(Bucket=settings.AWS_BUCKET_NAME, Key=o.get("Key"))
                logger.debug(f"Deleted object: {o.get('Key')}")
        logger.info("S3 bucket folder deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting S3 bucket folder: {e}")

def read_pdf(file_contents):
    logger.info("Reading PDF file contents")
    pages = []
    try:
        images = convert_from_bytes(file_contents)
        for i, image in enumerate(images):
            text = tess.image_to_string(image=image)
            pages.append(text)
        logger.debug("PDF content extracted successfully")
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
    return "\n".join(pages)

@traceable(
    run_type="llm",
    name="Generate question with legal pdf and question",
    project_name="adaletgpt",
)
def generate_question(pdf_contents, question):
    logger.info("Generating question with legal PDF and question")
    try:
        llm = ChatOpenAI(temperature=0.5, model_name=settings.LLM_MODEL_NAME)
        prompt = PromptTemplate.from_template(summary_legal_session_prompt_template)
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        response = llm_chain.invoke({"question": question, "pdf_contents": pdf_contents})
        logger.debug(f"Generated question: {response['text']}")
        return response["text"]
    except Exception as e:
        logger.error(f"Error generating question: {e}")
        return ""

def remove_sessions_by_user_id(user_id: int, db_session: Session):
    logger.info(f"Removing sessions for user_id: {user_id}")
    try:
        db_session.query(LegalSessionSummary).filter(
            LegalSessionSummary.user_id == user_id
        ).delete()

        db_session.query(LegalChatHistory).filter(
            LegalChatHistory.user_id == user_id
        ).delete()
        db_session.commit()
        logger.debug("Sessions and chat history removed from database")

        objects = s3_client.list_objects(
            Bucket=settings.AWS_BUCKET_NAME, Prefix=f"{user_id}"
        )
        if objects.get("Contents") is not None:
            for o in objects.get("Contents"):
                s3_client.delete_object(
                    Bucket=settings.AWS_BUCKET_NAME, Key=o.get("Key")
                )
                logger.debug(f"Deleted S3 object: {o.get('Key')}")

        session_id_array = (
            db_session.query(LegalSessionSummary.session_id)
            .filter(LegalSessionSummary.user_id == user_id)
            .all()
        )
        session_ids = [session_id for (session_id,) in session_id_array]
        logger.debug(f"Session IDs to clear from memory: {session_ids}")

        for session_id in session_ids:
            session_memory = init_postgres_chat_memory(session_id=session_id)
            if session_memory:
                session_memory.clear()
                logger.debug(f"Deleted session from memory: {session_id}")
        logger.info("All sessions removed successfully")
        return True
    except Exception as e:
        logger.error(f"Error removing sessions: {e}")
        return False

def check_shared_session_status(user_id: int, session_id: str, db_session: Session):
    logger.info(f"Checking shared session status for user_id: {user_id}, session_id: {session_id}")
    try:
        current_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.session_id == session_id,
            )
            .first()
        )
        if current_session:
            is_shared = current_session.is_shared
            shared_id = current_session.shared_id
            is_updatable = False
            if is_shared:
                updatable_messages = (
                    db_session.query(LegalChatHistory)
                    .filter(
                        LegalChatHistory.user_id == user_id,
                        LegalChatHistory.session_id == session_id,
                        LegalChatHistory.created_date >= current_session.shared_date,
                    )
                    .all()
                )
                is_updatable = len(updatable_messages) > 0
                logger.debug(f"Session is updatable: {is_updatable}")
            return is_shared, is_updatable, shared_id
        else:
            logger.warning("Session not found")
            return False, False, None
    except Exception as e:
        logger.error(f"Error checking shared session status: {e}")
        return False, False, None

def create_session_sharelink(user_id: int, session_id: str, db_session: Session):
    logger.info(f"Creating session share link for user_id: {user_id}, session_id: {session_id}")
    try:
        current_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.session_id == session_id,
            )
            .first()
        )
        if current_session is None:
            logger.warning("Session not found for sharing")
            raise HTTPException(
                status_code=400, detail="There is no Session. Invalid request."
            )

        current_session.is_shared = True
        shared_id = uuid.uuid4().hex
        current_session.shared_id = shared_id
        current_session.shared_date = datetime.now()
        shared_url = f"https://chat.adaletgpt.com/shared?shared_id={shared_id}"
        db_session.commit()
        logger.debug(f"Shared URL created: {shared_url}")
        return shared_url
    except Exception as e:
        logger.error(f"Error creating session share link: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def get_shared_session_messages(shared_id: str, db_session: Session):
    logger.info(f"Retrieving shared session messages for shared_id: {shared_id}")
    try:
        shared_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.is_shared == True,
                LegalSessionSummary.shared_id == shared_id,
            )
            .first()
        )
        if shared_session is None:
            logger.warning("Invalid shared link")
            raise HTTPException(status_code=400, detail="Invalid link.")

        user_id = shared_session.user_id
        session_id = shared_session.session_id
        session_summary = shared_session.summary
        shared_date = shared_session.shared_date

        messages: List[LegalMessage] = (
            db_session.query(LegalChatHistory)
            .filter(
                LegalChatHistory.user_id == user_id,
                LegalChatHistory.session_id == session_id,
                LegalChatHistory.created_date <= shared_date,
            )
            .order_by(LegalChatHistory.created_date.asc())
            .order_by(LegalChatHistory.id.asc())
            .all()
        )
        logger.debug(f"Retrieved {len(messages)} messages for shared session")
        return session_summary, messages, shared_date
    except Exception as e:
        logger.error(f"Error retrieving shared session messages: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def get_shared_sessions_by_user_id(
    user_id: int, db_session: Session
) -> List[SharedSessionSummary]:
    logger.info(f"Retrieving shared sessions for user_id: {user_id}")
    try:
        shared_sessions = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.is_shared == True,
            )
            .order_by(LegalSessionSummary.shared_date.desc())
            .all()
        )
        logger.debug(f"Found {len(shared_sessions)} shared sessions")
        return shared_sessions
    except Exception as e:
        logger.error(f"Error retrieving shared sessions: {e}")
        return []

def delete_shared_sessions_by_user_id(user_id: int, db_session: Session):
    logger.info(f"Deleting all shared sessions for user_id: {user_id}")
    try:
        db_session.query(LegalSessionSummary).filter(
            LegalSessionSummary.user_id == user_id,
            LegalSessionSummary.is_shared == True,
        ).update(
            {
                LegalSessionSummary.is_shared: False,
                LegalSessionSummary.shared_id: None,
                LegalSessionSummary.shared_date: None,
            }
        )
        db_session.commit()
        logger.debug("All shared sessions deleted successfully")
        return True
    except Exception as e:
        logger.error(f"Error deleting shared sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def delete_shared_session_by_id(user_id: int, session_id: str, db_session: Session):
    logger.info(f"Deleting shared session for user_id: {user_id}, session_id: {session_id}")
    try:
        shared_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.is_shared == True,
            )
            .first()
        )
        if shared_session is not None:
            shared_session.is_shared = False
            shared_session.shared_id = None
            shared_session.shared_date = None
            db_session.commit()
            logger.debug("Shared session deleted successfully")
            return True
        else:
            logger.warning("Invalid session_id or token for shared session deletion")
            raise HTTPException(status_code=400, detail="Invalid session_id or token")
    except Exception as e:
        logger.error(f"Error deleting shared session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def get_original_legal_case(case_id: str, data_type: str):
    logger.info(f"Retrieving original legal case for case_id: {case_id}, data_type: {data_type}")
    try:
        s3_key = f"{case_id}.{data_type}"
        data = s3_client.get_object(
            Bucket=settings.AWS_LEGALCASE_BUCKET_NAME, Key=s3_key
        )
        logger.debug("Original legal case retrieved successfully")
        return data
    except s3_client.exceptions.NoSuchKey:
        logger.warning("Legal case file does not exist")
        raise HTTPException(status_code=400, detail="Legal case file does not exist.")
    except Exception as e:
        logger.error(f"Error retrieving legal case: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def archive_session(user_id: int, session_id: str, db_session: Session):
    logger.info(f"Archiving session for user_id: {user_id}, session_id: {session_id}")
    try:
        current_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.session_id == session_id,
            )
            .first()
        )
        if current_session is None:
            logger.warning("Session not found for archiving")
            raise HTTPException(
                status_code=400, detail="There is no Session. Invalid request."
            )
        current_session.is_archived = True
        current_session.archived_date = datetime.now()
        db_session.commit()
        logger.debug("Session archived successfully")
        return True
    except Exception as e:
        logger.error(f"Error archiving session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def archive_all_session(user_id: int, db_session: Session):
    logger.info(f"Archiving all sessions for user_id: {user_id}")
    try:
        db_session.query(LegalSessionSummary).filter(
            LegalSessionSummary.user_id == user_id,
            LegalSessionSummary.is_archived == False,
        ).update(
            {
                LegalSessionSummary.is_archived: True,
                LegalSessionSummary.archived_date: datetime.now(),
            }
        )
        db_session.commit()
        logger.debug("All sessions archived successfully")
        return True
    except Exception as e:
        logger.error(f"Error archiving all sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def get_archived_sessions_by_user_id(
    user_id: int, db_session: Session
) -> List[ArchivedSessionSummary]:
    logger.info(f"Retrieving archived sessions for user_id: {user_id}")
    try:
        archived_sessions = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.is_archived == True,
            )
            .order_by(LegalSessionSummary.archived_date.desc())
            .all()
        )
        logger.debug(f"Found {len(archived_sessions)} archived sessions")
        return archived_sessions
    except Exception as e:
        logger.error(f"Error retrieving archived sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def delete_archived_session_by_id(user_id: int, session_id: str, db_session: Session):
    logger.info(f"Deleting archived session for user_id: {user_id}, session_id: {session_id}")
    try:
        archived_session = (
            db_session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.user_id == user_id,
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.is_archived == True,
            )
            .first()
        )
        if archived_session is not None:
            archived_session.is_archived = False
            archived_session.archived_date = None
            db_session.commit()
            logger.debug("Archived session deleted successfully")
            return True
        else:
            logger.warning("Invalid session_id or token for archived session deletion")
            raise HTTPException(status_code=400, detail="Invalid session_id or token")
    except Exception as e:
        logger.error(f"Error deleting archived session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

def delete_archived_sessions_by_user_id(user_id: int, db_session: Session):
    logger.info(f"Deleting all archived sessions for user_id: {user_id}")
    try:
        db_session.query(LegalSessionSummary).filter(
            LegalSessionSummary.user_id == user_id,
            LegalSessionSummary.is_archived == True,
        ).update(
            {
                LegalSessionSummary.is_archived: False,
                LegalSessionSummary.archived_date: None,
            }
        )
        db_session.commit()
        logger.debug("All archived sessions deleted successfully")
        return True
    except Exception as e:
        logger.error(f"Error deleting archived sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
