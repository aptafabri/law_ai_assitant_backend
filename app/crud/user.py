from models import User, TokenTable
from database.session import Base, engine, SessionLocal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserLogin, ChangePassword, UserInfo, SubscriptionInfo
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
from crud.notify import send_reset_password_mail, send_verify_email, send_subscription_expiry_notification
import asyncio
from core.utils import create_access_token
from models.session_summary_legal import LegalSessionSummary
from models import LegalChatHistory
from jinja2 import Template, Environment, FileSystemLoader
from io import BytesIO
import os
import zipfile
import boto3
from log_config import configure_logging
from core.auth_bearer import is_subscription_expired

# Configure logging
logger = configure_logging(__name__)

s3_client = boto3.client(
    service_name="s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
)

def create_user(user: UserCreate, session: Session):
    logger.info(f"Creating user with email: {user.email}")
    existing_user = session.query(User).filter_by(email=user.email).first()
    if existing_user:
        logger.warning(f"Email already registered: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    activated_by_admin = True
    
    try:
        encrypted_password = get_hashed_password(user.password)
        new_user = User(
            username=user.username, email=user.email, password=encrypted_password, activated_by_admin=activated_by_admin
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        token = create_access_token(new_user.id)
        send_verify_email(new_user.email, token)
        logger.info(f"User created successfully: {user.email}")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return False


def login_user(auth: UserLogin, session: Session):
    logger.info(f"Attempting login for email: {auth.email}")
    user = session.query(User).filter(User.email == auth.email).first()
    if user is None:
        logger.warning(f"Login failed: Incorrect Email {auth.email}")
        raise HTTPException(status_code=400, detail="Incorrect Email")

    if not verify_password(auth.password, user.password):
        logger.warning(f"Login failed: Incorrect Password for {auth.email}")
        raise HTTPException(status_code=400, detail="Incorrect Password")

    if user.is_active:
        if user.activated_by_admin:
            access = create_access_token(user.id)
            refresh = create_refresh_token(user.id)
            logger.info(f"Login successful for {auth.email}, tokens generated")

            token_db = TokenTable(
                user_id=user.id, access_token=access, refresh_token=refresh, status=True
            )
            session.add(token_db)
            session.commit()
            session.refresh(token_db)
            subscription_status = check_subscription_expiry_notification(user, session)
            return {
                "access_token": access,
                "refresh_token": refresh,
                "payment_status": subscription_status["payment_status"],
                "message": subscription_status["message"]
            }
            
            
        else:
            logger.warning(f"Access not allowed for {auth.email}, account not activated by admin")
            raise HTTPException(status_code=400, detail="Your access is not allowed. Please request your access to the support team.")
    else:
        logger.warning(f"Login failed: Email not verified for {auth.email}")
        raise HTTPException(status_code=400, detail="Email is not verified")


async def change_password(req: ChangePassword, session: Session):
    logger.info(f"Changing password for email: {req.email}")
    update_user = session.query(User).filter(User.email == req.email).first()
    if update_user is None:
        logger.warning(f"Change password failed: User not found {req.email}")
        raise HTTPException(status_code=400, detail="User not found.")

    if not verify_password(req.old_password, update_user.password):
        logger.warning(f"Change password failed: Incorrect old password for {req.email}")
        raise HTTPException(status_code=400, detail="Incorrect Password.")

    encrypted_password = get_hashed_password(req.new_password)
    update_user.password = encrypted_password
    session.commit()

    logger.info(f"Password changed successfully for {req.email}")
    return {"message": "Password changed successfully"}


async def logout_user(token: str, session: Session):
    logger.info("Processing logout for token")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        user_id = payload["sub"]

        token_record = session.query(TokenTable).all()
        expired_tokens = [
            record.user_id for record in token_record if (datetime.now() - record.created_date).days > 1
        ]

        if expired_tokens:
            session.query(TokenTable).filter(TokenTable.user_id.in_(expired_tokens)).delete()
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

        logger.info(f"Logout successful for user {user_id}")
        return {"message": "Logout Successfully"}
    except (ExpiredSignatureError, InvalidTokenError) as e:
        logger.error(f"Logout failed due to invalid token: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid token")


def get_userid_by_token(token: str) -> int:
    logger.debug("Decoding token to retrieve user ID")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        return int(payload["sub"])
    except InvalidTokenError as e:
        logger.error(f"Invalid token: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid token")


def get_user_info(token: str, session: Session):
    logger.info("Retrieving user info")
    try:
        user_id = get_userid_by_token(token)
        user_record = (
            session.query(User.email, User.username).filter(User.id == user_id).first()
        )

        if user_record:
            logger.info(f"User info retrieved for user {user_id}")
            return UserInfo(email=user_record[0], user_name=user_record[1])
        else:
            logger.warning(f"User not found with ID {user_id}")
            raise HTTPException(status_code=400, detail="User not found.")
    except Exception as e:
        logger.error(f"An error occurred while querying the database: {str(e)}")
        return []


def generate_verification_code():
    logger.debug("Generating verification code")
    return secrets.token_hex(3)


def reset_password_request(email: str, session: Session):
    logger.info(f"Processing password reset request for {email}")
    update_user = session.query(User).filter(User.email == email).first()
    if update_user is None:
        logger.warning(f"Reset password request failed: User not found {email}")
        raise HTTPException(status_code=400, detail="User not found.")

    verify_code = generate_verification_code()
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

    logger.info(f"Password reset code sent to {email}")
    return {"message": "Password reset code sent.", "access_token": access_token}


def verify_forgot_code(token: str, code: str, session: Session):
    logger.info("Verifying forgot code")
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id == user_id).first()

    if user is None:
        logger.warning(f"User not found during forgot code verification {user_id}")
        raise HTTPException(status_code=400, detail="User not found.")

    if user.verify_code == code and user.verify_code_expiry > datetime.now():
        user.reset_verified = True
        session.commit()
        logger.info(f"Verification code for reset password matched for {user_id}")
        return True
    else:
        logger.warning(f"Invalid or expired verification code for {user_id}")
    return False


def reset_password(token: str, new_password: str, session: Session):
    logger.info(f"Resetting password for token {token}")
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"Reset password failed: User not found {user_id}")
        raise HTTPException(status_code=400, detail="User not found.")

    if not user.reset_verified:
        logger.warning(f"Reset password request invalid for {user_id}")
        raise HTTPException(status_code=400, detail="Invalid request")

    encrypted_password = get_hashed_password(new_password)
    user.password = encrypted_password
    user.verify_code = None
    user.verify_code_expiry = None
    user.reset_verified = False
    session.commit()

    session.query(TokenTable).filter(
        TokenTable.user_id == user_id, TokenTable.access_token == token
    ).delete()
    session.commit()

    logger.info(f"Password reset successfully for user {user_id}")
    return {"message": "Password reset successfully"}


def get_user_by_email(db: Session, email: str):
    logger.info(f"Fetching user by email: {email}")
    return db.query(User).filter(User.email == email).first()


def verify_register_token(token: str):
    logger.info("Verifying register token")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        logger.info(f"Token verified successfully, payload: {payload}")
        return payload["sub"], False
    except ExpiredSignatureError:
        logger.warning("Token has expired, decoding without verification")
        try:
            payload = jwt.decode(
                token,
                key=settings.JWT_SECRET_KEY,
                options={"verify_exp": False},
                algorithms=settings.ALGORITHM,
            )
            return payload["sub"], True
        except InvalidTokenError as e:
            logger.error(f"Invalid token: {str(e)}")
            return None, None
    except InvalidTokenError as e:
        logger.error(f"Invalid token: {str(e)}")
        return None, None


def export_data_by_user_id(user_id: int, db_session: Session):
    logger.info(f"Exporting data for user ID {user_id}")
    chat_history = (
        db_session.query(LegalChatHistory)
        .filter(LegalChatHistory.user_id == user_id)
        .order_by(LegalChatHistory.created_date.asc())
        .all()
    )
    session_summaries = (
        db_session.query(LegalSessionSummary)
        .filter(LegalSessionSummary.user_id == user_id)
        .order_by(LegalSessionSummary.created_date.desc())
        .all()
    )
    chat_history_dict = {}
    for session in session_summaries:
        session_id = session.session_id
        if session_id not in chat_history_dict:
            chat_history_dict[session_id] = {"summary": session.summary, "messages": []}
    for message in chat_history:
        session_id = message.session_id
        chat_history_dict[session_id]["messages"].append(
            {"content": message.content, "role": message.role}
        )
    logger.info(f"Data export completed for user ID {user_id}")
    return chat_history_dict


def export_data(user_id: int, db_session: Session):
    logger.info(f"Processing data export for user {user_id}")
    try:
        chat_history_dict = export_data_by_user_id(user_id=user_id, db_session=db_session)
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
        s3_url = f"https://{settings.AWS_EXPORTDATA_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        logger.info(f"Data export uploaded to S3 for user {user_id}")
        return s3_url
    except Exception as e:
        logger.error(f"Error during data export for user {user_id}: {str(e)}")
        return None


async def calculate_llm_token(user_id: int, db_session: Session, total_llm_tokens: int):
    logger.info(f"Calculating LLM token for user {user_id}")
    try:
        update_user = db_session.query(User).filter(User.id == user_id).first()
        if update_user is None:
            logger.warning(f"LLM token calculation failed: User not found {user_id}")
            raise HTTPException(status_code=400, detail="User not found.")

        current_llm_tokens = update_user.llm_token * 1000
        current_llm_tokens = (current_llm_tokens - total_llm_tokens) / 1000
        update_user.llm_token = current_llm_tokens
        db_session.commit()
        logger.info(f"LLM token updated for user {user_id}")
    except SQLAlchemyError as e:
        logger.error(f"Error updating LLM token for user {user_id}: {str(e)}")
        db_session.rollback()


def get_user_subscription_info(user_id: int, session: Session) -> SubscriptionInfo:
    logger.info(f"Retrieving subscription info for user_id: {user_id}")
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found with ID {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
            
        if user.subscription_plan is None or user.subscription_expiry is None:
            return SubscriptionInfo(
                message="User has no subscription plan.",
                is_active=False
            )
            
        is_active = not is_subscription_expired(user.subscription_expiry)
        message = "Subscription is active." if is_active else "Subscription has expired."
        
        return SubscriptionInfo(
            subscription_plan=user.subscription_plan,
            subscription_expiry=user.subscription_expiry,
            is_active=is_active,
            daily_usage = user.daily_chat_count,
            message=message
        )
    except Exception as e:
        logger.error(f"Error retrieving subscription info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def check_subscription_expiry_notification(user: User, session: Session) -> dict:
    if user.subscription_plan is None or user.subscription_expiry is None:
        return {
            "message": "User has no subscription plan.",
            "payment_status": False
        }
        
    current_time = datetime.now()
    days_until_expiry = (user.subscription_expiry - current_time).days

    # Check if we've already sent a notification recently (within last 5 days)
    notification_already_sent = (
        user.last_expiry_notification_sent is not None
        and (current_time - user.last_expiry_notification_sent).days < 5
    )
    print("notification_already_sent",notification_already_sent)

    if days_until_expiry <= 5 and days_until_expiry > 0 and not notification_already_sent:
        # Send notification email with custom message for upcoming expiry
        send_subscription_expiry_notification(
            recipient_email=user.email,
            days_remaining=days_until_expiry,
            subscription_plan=user.subscription_plan,
            status_message=f"Your {user.subscription_plan} subscription will expire in {days_until_expiry} days. Please renew to continue using our services."
        )
        # Update the last notification sent timestamp
        user.last_expiry_notification_sent = current_time
        session.commit()
        
        message = f"Subscription will expire in {days_until_expiry} days."
        payment_status = True
    elif days_until_expiry <= 0 and not notification_already_sent:
        # Send notification email with custom message for expired subscription
        send_subscription_expiry_notification(
            recipient_email=user.email,
            days_remaining=0,
            subscription_plan=user.subscription_plan,
            status_message=f"Your {user.subscription_plan} subscription has expired. Please renew to restore access to all features."
        )
        # Update the last notification sent timestamp
        user.last_expiry_notification_sent = current_time
        session.commit()
        
        message = "Subscription has expired."
        payment_status = False
    else:
        message = "Subscription is active." if days_until_expiry > 5 else f"Subscription will expire in {days_until_expiry} days."
        payment_status = days_until_expiry > 0
        
    return {
        "message": message,
        "payment_status": payment_status
    }

async def check_daily_chat_limit(user_id: int, db_session: Session) -> bool:
    print("check_daily_chat_limit",user_id)
    user = db_session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    current_time = datetime.now()
    if user.last_chat_reset.date() < current_time.date():
        user.daily_chat_count = 0
        user.last_chat_reset = current_time
    if user.daily_chat_count >= settings.DAILY_CHAT_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Daily chat limit reached. Please try again tomorrow."
        )
    print("user.daily_chat_count",user.daily_chat_count)
    user.daily_chat_count += 1
    db_session.commit()
    
    return True
    