import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from langchain_openai import ChatOpenAI
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
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
from schemas.message import ChatAdd, SessionSummary, LegalMessage, LegalChatAdd
from core.config import settings
from core.prompt import summary_legal_session_prompt_template
from langsmith import traceable

# tess.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tess.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"


s3_client = boto3.client(
    service_name="s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
)


def get_sessions_by_userid(user_id: int, session: Session) -> List[SessionSummary]:

    session_summary_array: List[SessionSummary] = []
    results = (
        session.query(LegalSessionSummary)
        .filter(LegalSessionSummary.user_id == user_id)
        .order_by(LegalSessionSummary.favourite_date.desc())
        .all()
    )
    session_summary_array = results
    return session_summary_array


def get_messages_by_session_id(
    user_id: int, session_id: str, session: Session
) -> List[LegalMessage]:

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

        return message_array
    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []


def get_latest_messages_by_userid(user_id: int, session: Session) -> List[LegalMessage]:
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


def add_legal_message(message: ChatAdd, session: Session):

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
    except SQLAlchemyError as e:
        print("An error occurred while adding a message to the database:", str(e))
        session.rollback()


def add_legal_chat_message(message: LegalChatAdd, session: Session):

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
    except SQLAlchemyError as e:
        print("An error occurred while adding a message to the database:", str(e))
        session.rollback()


def remove_messages_by_session_id(user_id: int, session_id: str, session: Session):

    try:

        session_messages = (
            session.query(LegalChatHistory)
            .filter(
                LegalChatHistory.session_id == session_id,
                LegalChatHistory.user_id == user_id,
            )
            .delete(synchronize_session=False)
        )
        session.commit()

        # message_ids = [msg_id for (msg_id,) in session_messages]

        # session.query(LegalChatHistory).filter(
        #     LegalChatHistory.id.in_(message_ids)
        # ).delete(synchronize_session=False)
        return {"message": "Deleted session successfully."}

    except SQLAlchemyError as e:
        print("An error occurred while querying the database:", str(e))
        return []


def summarize_session(question: str, answer: str):
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

    response = llm_chain.invoke({"question": question, "answer": answer})

    return response["text"]


def add_legal_session_summary(
    session_id: str, user_id: int, summary: str, session: Session
):

    chat_session_db = LegalSessionSummary(
        user_id=user_id, session_id=session_id, summary=summary
    )
    session.add(chat_session_db)
    session.commit()
    session.refresh(chat_session_db)

    return {"session_id": session_id, "summary": summary}


def remove_session_summary(session_id: str, session: Session):

    existing_session_summary = (
        session.query(LegalSessionSummary)
        .filter(LegalSessionSummary.session_id == session_id)
        .delete()
    )
    session.commit()


def legal_session_exist(session_id: str, session: Session):
    existing_session = (
        session.query(LegalSessionSummary)
        .filter(LegalSessionSummary.session_id == session_id)
        .first()
    )
    if existing_session:
        return True
    else:
        return False


def upvote_chat_session(session_id: str, user_id: int, session: Session):
    try:
        update_session = (
            session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.user_id == user_id,
            )
            .first()
        )

        update_session.is_favourite = True
        update_session.favourite_date = datetime.now()

        session.commit()

        return {"success": True}

    except SQLAlchemyError as e:

        return {"success": False}


def devote_chat_session(session_id: str, user_id: int, session: Session):
    try:
        update_session = (
            session.query(LegalSessionSummary)
            .filter(
                LegalSessionSummary.session_id == session_id,
                LegalSessionSummary.user_id == user_id,
            )
            .first()
        )

        update_session.is_favourite = False
        update_session.favourite_date = update_session.created_date

        session.commit()

        return {"success": True}

    except SQLAlchemyError as e:

        return {"success": False}


def init_postgres_legal_chat_memory(session_id: str):
    table_name = "legal_message_store"
    sync_connection = psycopg.connect(settings.POSTGRES_CHAT_HISTORY_URI)
    PostgresChatMessageHistory.create_tables(sync_connection, table_name)
    chat_memory = PostgresChatMessageHistory(
        table_name, session_id, sync_connection=sync_connection
    )

    return chat_memory


def upload_legal_description(file_content, user_id, session_id, legal_s3_key):
    s3_key = f"{user_id}/{session_id}/{legal_s3_key}"
    s3_client.put_object(Bucket=settings.AWS_BUCKET_NAME, Body=file_content, Key=s3_key)


def download_legal_description(user_id, session_id, legal_s3_key):
    s3_key = f"{user_id}/{session_id}/{legal_s3_key}"
    print("s3_key:", s3_key)
    data = s3_client.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=s3_key)

    return data


def delete_s3_bucket_folder(user_id, session_id):
    objects = s3_client.list_objects(
        Bucket=settings.AWS_BUCKET_NAME, Prefix=f"{user_id}/{session_id}"
    )
    print(objects)
    if objects.get("Contents") is not None:
        for o in objects.get("Contents"):
            s3_client.delete_object(Bucket=settings.AWS_BUCKET_NAME, Key=o.get("Key"))


def read_pdf(file_contents):
    pages = []
    try:
        # images = convert_from_bytes(
        #     file_contents,
        #     poppler_path=r"C:\Program Files\Release-24.02.0-0\poppler-24.02.0\Library\bin",
        # )
        images = convert_from_bytes(file_contents)
        # Extract text from each image
        for i, image in enumerate(images):
            text = tess.image_to_string(image=image)
            pages.append(text)

    except Exception as e:
        print(e)
    return "\n".join(pages)


@traceable(
    run_type="llm",
    name="Generate question with legal pdf and question",
    project_name="adaletgpt",
)
def generate_question(pdf_contents, question):
    llm = ChatOpenAI(temperature=0.5, model_name=settings.LLM_MODEL_NAME)
    prompt = PromptTemplate.from_template(summary_legal_session_prompt_template)

    # Define LLM chain
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    response = llm_chain.invoke({"question": question, "pdf_contents": pdf_contents})

    return response["text"]


def remove_sessions_by_user_id(user_id: int, db_session: Session):
    try:
        ## remove session summary ####
        db_session.query(LegalSessionSummary).filter(
            LegalSessionSummary.user_id == user_id
        ).delete()

        ## remove chathistory
        db_session.query(LegalChatHistory).filter(
            LegalChatHistory.user_id == user_id
        ).delete()
        db_session.commit()
        ## remove legal pdfs in s3 bucket
        objects = s3_client.list_objects(
            Bucket=settings.AWS_BUCKET_NAME, Prefix=f"{user_id}"
        )
        if objects.get("Contents") is not None:
            for o in objects.get("Contents"):
                s3_client.delete_object(
                    Bucket=settings.AWS_BUCKET_NAME, Key=o.get("Key")
                )
        session_id_array = (
            db_session.query(LegalSessionSummary.session_id)
            .filter(LegalSessionSummary.user_id == user_id)
            .all()
        )
        session_ids = [session_id for (session_id,) in session_id_array]
        print("session_id array:", session_ids, len(session_ids))
        for session_id in session_ids:
            session_memory = init_postgres_legal_chat_memory(session_id=session_id)
            session_memory.clear()
            print("Deleted session:", session_id)
        return True
    except Exception as e:
        print("Error:", e)
        return False
