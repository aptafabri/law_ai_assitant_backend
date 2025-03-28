from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from fastapi import APIRouter
from jinja2 import Environment, FileSystemLoader
from io import BytesIO
import os
import zipfile
from log_config import configure_logging
from datetime import datetime

from crud.user import (
    create_user,
    login_user,
    change_password,
    reset_password,
    logout_user,
    get_user_info,
    reset_password_request,
    verify_forgot_code,
    get_userid_by_token,
    verify_register_token,
    export_data,
)
from schemas.user import (
    UserCreate,
    UserLogin,
    ChangePassword,
    UserInfo,
    ResetPasswordRequest,
    ForgotPasswordRequest,
    VerificationCodeRequest,
    ResendVerificationRequest,
)
from crud.chat import remove_sessions_by_user_id
from crud.notify import send_verify_email, send_export_email
from core.auth_bearer import JWTBearer
from core.pay_bearer import AUTHBearer
from models import User, TokenTable
from database.session import get_session
from core.utils import create_access_token

router = APIRouter()

# Configure logging
logger = configure_logging(__name__)


@router.post("/register", tags=["User controller"])
def register(user: UserCreate, session: Session = Depends(get_session)):
    logger.info(f"Registering user with email: {user.email}")
    created_status = create_user(user, session)

    if created_status == True:
        logger.info(f"User registered successfully: {user.email}")
        return JSONResponse(
            content={"message": "Registered successfully."}, status_code=200
        )
    else:
        logger.error(f"Failed to register user: {user.email}")
        return JSONResponse(
            content={"message": "Internal Server Error"}, status_code=500
        )


@router.post("/login", tags=["User controller"], status_code=200)
async def login(user: UserLogin, session: Session = Depends(get_session)):
    logger.info(f"User login attempt: {user.email}")
    token_info = login_user(user, session)
    if "access_token" in token_info:
        logger.info(f"User logged in successfully: {user.email}")
    else:
        logger.warning(f"Failed login attempt for user: {user.email}")
    return JSONResponse(content=token_info, status_code=200)


@router.get("/getusers", tags=["User controller"], status_code=200)
async def getusers(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    logger.info("Fetching all users.")
    users = session.query(User).all()
    logger.debug(f"Retrieved users: {users}")
    return users


@router.post("/change-password", tags=["User controller"], status_code=200)
async def password_change(
    user: ChangePassword,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    try:
        logger.info(f"Password change request for user ID: {user.user_id}")
        change_info = await change_password(user, session)
        return JSONResponse(content=change_info, status_code=200)
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Internal Server Error:{e}")

@router.post("/logout", tags=["User controller"], status_code=200)
async def logout(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    try:  
        logger.info(f"Logout request with token: {dependencies}")
        token = dependencies
        logout_info = await logout_user(token, session)
        return JSONResponse(content=logout_info, status_code=200)
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Internal Server Error:{e}")


@router.post("/get-user-information", response_model=UserInfo, tags=["User controller"])
def get_user(
    access_token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    logger.info("Fetching user information.")
    user_info = get_user_info(access_token, session)
    if user_info:
        logger.debug(f"User info retrieved: {user_info}")
    else:
        logger.warning("Failed to retrieve user information.")
    return user_info


@router.post("/refresh", tags=["User controller"])
async def refresh(dependencies=Depends(JWTBearer())):
    logger.info("Token refresh request.")
    return JSONResponse(content={"access_token": dependencies}, status_code=200)


@router.post("/request_password_reset", tags=["User controller"])
def request_password_reset(
    req: ForgotPasswordRequest, session: Session = Depends(get_session)
):
    try:
        logger.info(f"Password reset request for email: {req.email}")
        email_status = reset_password_request(email=req.email, session=session)
        print("status:",email_status, email_status.get("successs"))
        return JSONResponse(content=email_status, status_code=200)        
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Internal Server Error:{e}")


@router.post("/verify-code", tags=["User controller"])
def verify_reset_code(
    req: VerificationCodeRequest,
    dependencies=Depends(AUTHBearer()),
    session: Session = Depends(get_session),
):
    logger.info("Verifying reset code.")
    try:
        if not verify_forgot_code(dependencies, req.verify_code, session=session):
            logger.warning("Invalid verification code provided.")
            raise HTTPException(status_code=400, detail="Invalid request")
        logger.info("Verification code is valid.")
        return {"message": "Verification code is valid"}
    except Exception as e:
        logger.exception(f"An error occurred during code verification: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/reset-password", tags=["User controller"])
def password_reset(
    req: ResetPasswordRequest,
    dependencies=Depends(AUTHBearer()),
    session: Session = Depends(get_session),
):
    try:
        logger.info("Password reset request.")
        reset_info = reset_password(
            token=dependencies, new_password=req.new_password, session=session
        )
        return JSONResponse(content=reset_info, status_code=200)
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Internal Server Error:{e}")
        


@router.post("/delete-account", tags=["User controller"])
def delete_account(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    logger.info(f"Account deletion request for user ID: {user_id}")
    if remove_sessions_by_user_id(user_id=user_id, db_session=session) == True:
        try:
            session.query(User).filter(User.id == user_id).delete()
            session.query(TokenTable).filter(TokenTable.user_id == user_id).delete()
            session.commit()
            logger.info(f"Account deleted for user ID: {user_id}")
            return JSONResponse(
                content={"Success": True, "message": "Deleted account."},
                status_code=200,
            )
        except Exception as e:
            logger.exception(f"Error deleting account for user ID {user_id}: {e}")
            return JSONResponse(
                content={"Success": False, "message": " Internal Server Error."},
                status_code=500,
            )
    else:
        logger.error(f"Failed to remove sessions for user ID: {user_id}")
        return JSONResponse(
            content={"Success": False, "message": " Internal Server Error."},
            status_code=500,
        )


@router.get("/verify", tags=["User controller"])
def verify(token: str, session: Session = Depends(get_session)):
    logger.info(f"Email verification request with token: {token}")
    id, expired = verify_register_token(token)
    if id is None and expired is None:
        logger.warning("Invalid verification token provided.")
        raise HTTPException(status_code=404, detail="Invalid token")
    else:
        if expired == False:
            user = session.query(User).filter(User.id == int(id)).first()
            if user:
                user.is_active = True
                user.created_date = datetime.now()
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.info(f"Email verified successfully for user ID: {id}")
                return JSONResponse(
                    content={"message": "Email verified successfully"}, status_code=200
                )
            else:
                logger.error(f"User not found with ID: {id}")
                raise HTTPException(status_code=404, detail="User not found")
        elif expired == True:
            logger.warning("Verification token has expired.")
            raise HTTPException(status_code=400, detail="Expired token")


@router.post("/resend-verification", tags=["User controller"])
def resend_verification_email(
    request: ResendVerificationRequest, session: Session = Depends(get_session)
):
    logger.info("Resend verification email request.")
    id, _ = verify_register_token(request.token)
    if id is not None:
        user = session.query(User).filter(User.id == id).first()
        if not user:
            logger.error(f"User not found with ID: {id}")
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_active == True:
            logger.warning(f"User already verified with ID: {id}")
            raise HTTPException(status_code=400, detail="User already verified")
        try:
            token = create_access_token(user.id)
            send_verify_email(recipient_email=user.email, token=token)
            logger.info(f"Verification email resent to: {user.email}")
            return JSONResponse(
                content={"message": "Verification email resent"}, status_code=200
            )
        except Exception as e:
            logger.exception(f"Error resending verification email: {e}")
            return JSONResponse(
                content={"message": "Internal Server Error"}, status_code=500
            )
    else:
        logger.warning("Invalid token provided for resending verification email.")
        raise HTTPException(status_code=400, detail="Invalid token")


@router.post("/request-exporting-data", tags=["User Controller"])
def request_exporting_data(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    logger.info("Data export request.")
    user_id = get_userid_by_token(dependencies)
    current_user = session.query(User).filter(User.id == user_id).first()
    if current_user is None:
        logger.error(f"User not found with ID: {user_id}")
        raise HTTPException(status_code=400, detail="User not found")
    try:
        s3_url = export_data(user_id=user_id, db_session=session)
        send_export_email(recipient_email=current_user.email, url=s3_url)
        if s3_url is not None:
            logger.info(f"Data export request processed for user ID: {user_id}")
            return JSONResponse(
                content={"message": "Export request sent."}, status_code=200
            )
        else:
            logger.error("Failed to generate S3 URL for data export.")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    except Exception as e:
        logger.exception(f"Error processing data export request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
