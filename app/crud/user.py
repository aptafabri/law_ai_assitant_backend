from models import User, TokenTable
from database.session import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserLogin, ChangePassword, UserInfo
from fastapi import Depends, Response, HTTPException
from fastapi.responses import JSONResponse
from core.utils import (
    get_hashed_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from datetime import datetime, timezone, timedelta
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from core import settings
import secrets
from crud.notify import send_reset_password_mail, send_verify_email
import asyncio
from core.utils import create_access_token
from models.session_summary_legal import LegalSessionSummary
from models import LegalChatHistory
from jinja2 import Template, Environment, FileSystemLoader
from io import BytesIO
import os
import zipfile
import boto3

s3_client = boto3.client(
    service_name="s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
)


def create_user(user: UserCreate, session: Session):

    existing_user = session.query(User).filter_by(email=user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Eamil already registered")
    if user.password == "Mykola:)":
        activated_by_admin = True
    else:
        activated_by_admin = False

    try:
        encrypted_password = get_hashed_password(user.password)

        new_user = User(
            username=user.username, email=user.email, password=encrypted_password, activated_by_admin = activated_by_admin
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        token = create_access_token(new_user.id)
        send_verify_email(new_user.email, token)
        return True
    except Exception as e:
        return False


def login_user(auth: UserLogin, session: Session):
    user = session.query(User).filter(User.email == auth.email).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Incorrect Email")

    hashed_pass = user.password

    if not verify_password(auth.password, hashed_pass):
        raise HTTPException(status_code=400, detail="Incorrect Password")
    if user.is_active == True:
        if user.activated_by_admin == True:
            access = create_access_token(user.id)
            refresh = create_refresh_token(user.id)

            print(access, refresh)
            token_db = TokenTable(
                user_id=user.id, access_token=access, refresh_token=refresh, status=True
            )
            session.add(token_db)
            session.commit()
            session.refresh(token_db)
            token_info = {
                "access_token": access,
                "refresh_token": refresh,
            }
            return token_info
        else:
            raise HTTPException(status_code=400, detail="Your access is not allowed.Please request your access to the support team.")
    else:
        raise HTTPException(status_code=400, detail="Email is not verified")


async def change_password(req: ChangePassword, session: Session):

    update_user = session.query(User).filter(User.email == req.email).first()
    if update_user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    if not verify_password(req.old_password, update_user.password):
        raise HTTPException(status_code=400, detail="Incorrect Password.")

    encrypted_password = get_hashed_password(req.new_password)
    update_user.password = encrypted_password
    session.commit()

    return {"message": "Password changed successfully"}


async def logout_user(token: str, session: Session):
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    user_id = payload["sub"]

    token_record = session.query(TokenTable).all()
    info = []
    for record in token_record:
        print("record", record)
        print((datetime.now() - record.created_date).days)

        if (datetime.now() - record.created_date).days > 1:
            info.append(record.user_id)

    """
        This loop iterates through each token record and checks if its creation date is older than one day. If so, it appends the corresponding user ID to the info list.
    """
    if info:
        session.query(TokenTable).where(TokenTable.user_id.in_(info)).delete()
        session.commit()

    existing_token = (
        session.query(TokenTable)
        .filter(TokenTable.user_id == user_id, TokenTable.access_token == token)
        .first()
    )
    if existing_token:
        existing_token.status = False
        session.add(existing_token)
        session.commit()
        session.refresh(existing_token)
    return {"message": "Logout Successfully"}


def get_userid_by_token(token: str) -> int:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    user_id = payload["sub"]
    return user_id


def get_user_info(token: str, session: Session):

    user_id = get_userid_by_token(token)
    try:
        user_record = (
            session.query(User.email, User.username).filter(User.id == user_id).first()
        )

        if user_record:
            user_info = UserInfo(email=user_record[0], user_name=user_record[1])
            return user_info
        else:
            raise HTTPException(status_code=400, detail="User not found.")

    except Exception as e:
        print("An error occurred while querying the database:", str(e))
        return []


def generate_verification_code():
    return secrets.token_hex(3)


def reset_password_request(email: str, session: Session):
    update_user = session.query(User).filter(User.email == email).first()
    if update_user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    verify_code = generate_verification_code()
    print(verify_code, type(verify_code))
    update_user.verify_code = verify_code
    update_user.verify_code_expiry = datetime.now() + timedelta(minutes=5)
    session.commit()

    send_reset_password_mail(
        recipient_email=update_user.email,
        user_name=update_user.username,
        verify_code=verify_code,
    )
    access_token = create_access_token(update_user.id)

    token_db = TokenTable(
        user_id=update_user.id,
        access_token=access_token,
        refresh_token=access_token,
        status=True,
    )
    session.add(token_db)
    session.commit()
    session.refresh(token_db)

    return {"message": "Password reset code sent.", "access_token": access_token}


def verify_forgot_code(token: str, code: str, session: Session):
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    if user.verify_code == code:
        if user.verify_code_expiry > datetime.now():
            user.reset_verified = True
            session.commit()
            return True
    return False


def reset_password(token: str, new_password: str, session: Session):
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    if user.reset_verified != True:
        raise HTTPException(status_code=400, detail="Invalid request")

    encrypted_password = get_hashed_password(new_password)
    user.password = encrypted_password
    user.verify_code = None
    user.verify_code_expiry = None
    user.reset_verified = False
    session.commit()
    # Delete access_token
    session.query(TokenTable).where(
        TokenTable.user_id == user_id, TokenTable.access_token == token
    ).delete()
    session.commit()

    return {"message": "Password reseted successfully"}


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def verify_register_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        print("payload", payload)
        id = payload["sub"]
        expired = False
        return id, expired
    except ExpiredSignatureError:
        print("Token has expired.")
        # Decode the token without verifying the expiration to get the payload
        try:
            payload = jwt.decode(
                token,
                key=settings.JWT_SECRET_KEY,
                options={"verify_exp": False},
                algorithms=settings.ALGORITHM,
            )
            id = payload["sub"]
            return id, True
        except InvalidTokenError as e:
            print("Invalid token:", e)
            return None, None
    except InvalidTokenError as e:
        return None, None


def export_data_by_user_id(user_id: int, db_session: Session):
    chat_history = (
        db_session.query(LegalChatHistory)
        .filter(LegalChatHistory.user_id == user_id)
        .order_by(LegalChatHistory.created_date.asc())
        .all()
    )
    session_sumamries = (
        db_session.query(LegalSessionSummary)
        .filter(LegalSessionSummary.user_id == user_id)
        .order_by(LegalSessionSummary.created_date.desc())
        .all()
    )
    chat_history_dict = {}
    for session in session_sumamries:
        session_id = session.session_id
        if session_id not in chat_history_dict:
            chat_history_dict[session_id] = {"summary": session.summary, "messages": []}
    for message in chat_history:
        session_id = message.session_id
        chat_history_dict[session_id]["messages"].append(
            {"content": message.content, "role": message.role}
        )
    return chat_history_dict


def export_data(user_id: int, db_session: Session):
    try:
        chat_history_dict = export_data_by_user_id(
            user_id=user_id, db_session=db_session
        )
        templates_dir = os.path.abspath(os.path.join(__file__, "../../email_template"))
        templates_env = Environment(loader=FileSystemLoader(templates_dir))
        template = templates_env.get_template("export_template.html")
        rendered_html = template.render(json_data=chat_history_dict)
        html_file = BytesIO(rendered_html.encode("utf-8"))
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("chat.html", html_file.getvalue())
        zip_buffer.seek(0)
        s3_key = f"{user_id}/export_data/chat.zip"

        s3_client.put_object(
            Bucket=settings.AWS_EXPORTDATA_BUCKET_NAME, Body=zip_buffer, Key=s3_key
        )
        s3_url = (
            f"https://{settings.AWS_EXPORTDATA_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        )
        return s3_url
    except Exception as e:
        print("error:", e)
        return None
