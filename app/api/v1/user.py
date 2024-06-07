from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
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
from crud.notify import send_verify_email
from core.auth_bearer import JWTBearer
from models import User, TokenTable
from database.session import get_session
from core.utils import create_access_token

router = APIRouter()
from fastapi.responses import JSONResponse


@router.post("/register", tags=["User controller"])
def register(user: UserCreate, session: Session = Depends(get_session)):

    created_status = create_user(user, session)

    if created_status == True:
        return JSONResponse(
            content={"message": "Registered successfully."}, status_code=200
        )
    else:
        return JSONResponse(
            content={"message": "Internal Server Error"}, status_code=500
        )


@router.post("/login", tags=["User controller"], status_code=200)
async def login(user: UserLogin, session: Session = Depends(get_session)):
    token_info = login_user(user, session)
    return JSONResponse(content=token_info, status_code=200)


@router.get("/getusers", tags=["User controller"], status_code=200)
async def getusers(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    users = session.query(User).all()
    return users


@router.post("/change-password", tags=["User controller"], status_code=200)
async def password_change(
    user: ChangePassword,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    change_info = await change_password(user, session)
    return JSONResponse(content=change_info, status_code=200)


@router.post("/logout", tags=["User controller"], status_code=200)
async def logout(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    print("token:", dependencies)
    token = dependencies
    logout_info = await logout_user(token, session)
    return JSONResponse(content=logout_info, status_code=200, tags=["User controller"])


@router.post("/get-user-information", response_model=UserInfo, tags=["User controller"])
def get_user(
    access_token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_info = get_user_info(access_token, session)
    return user_info


@router.post("/refresh", tags=["User controller"])
async def refresh(dependencies=Depends(JWTBearer())):
    return JSONResponse(content={"access_token": dependencies}, status_code=200)


@router.post("/request_password_reset", tags=["User controller"])
def request_password_reset(
    req: ForgotPasswordRequest, session: Session = Depends(get_session)
):
    email_status = reset_password_request(email=req.email, session=session)
    return JSONResponse(content=email_status, status_code=200)


@router.post("/verify-code", tags=["User controller"])
def verify_reset_code(
    req: VerificationCodeRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    if not verify_forgot_code(dependencies, req.verify_code, session=session):
        raise HTTPException(status_code=400, detail="Invalid request")

    return {"message": "Verification code is valid"}


@router.post("/reset-password", tags=["User controller"])
def password_reset(
    req: ResetPasswordRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):

    reset_info = reset_password(
        token=dependencies, new_password=req.new_password, session=session
    )
    return JSONResponse(content=reset_info, status_code=200)


@router.post("/delete-account", tags=["User controller"])
def delete_account(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    if remove_sessions_by_user_id(user_id=user_id, db_session=session) == True:
        try:
            session.query(User).filter(User.id == user_id).delete()
            session.query(TokenTable).filter(TokenTable.user_id == user_id).delete()
            session.commit()
            return JSONResponse(
                content={"Success": True, "message": "Deleted account."},
                status_code=200,
            )
        except Exception as e:
            print("error:", e)
            return JSONResponse(
                content={"Success": False, "message": " Internal Server Error."},
                status_code=500,
            )
    else:
        return JSONResponse(
            content={"Success": False, "message": " Internal Server Error."},
            status_code=500,
        )


@router.get("/verify", tags=["User controller"])
def verify(token: str, session: Session = Depends(get_session)):
    print("token:", token)
    id, expired = verify_register_token(token)

    if id is None and expired is None:
        raise HTTPException(status_code=404, detail="Invalid token")
    else:
        if expired == False:
            user = session.query(User).filter(User.id == id).first()

            user.is_active = True
            session.add(user)
            session.commit()
            session.refresh(user)
            return JSONResponse(
                content={"message": "Email verified successfully"}, status_code=200
            )
        elif expired == True:
            raise HTTPException(status_code=400, detail="Expired token")


@router.post("/resend-verification", tags=["User controller"])
def resend_verification_email(
    request: ResendVerificationRequest, session: Session = Depends(get_session)
):
    id, _ = verify_register_token(request.token)
    print("user_id", id)
    if id is not None:
        user = session.query(User).filter(User.id == id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_active == True:
            raise HTTPException(status_code=400, detail="User already verified")
        try:
            token = create_access_token(user.id)
            send_verify_email(recipient_email=user.email, token=token)
            return JSONResponse(
                content={"message": "Verification email resent"}, status_code=200
            )
        except Exception as e:
            return JSONResponse(
                content={"message": "Internal Server Error"}, status_code=500
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid token")
