from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from crud.user import create_user, login_user, change_password,reset_password, logout_user, get_user_info, reset_password_request, verify_forgot_code
from schemas.user import UserCreate, UserLogin, ChangePassword, UserInfo, ResetPasswordRequest, ForgotPasswordRequest, VerificationCodeRequest
from core.auth_bearer import JWTBearer
from models import User
from database.session import get_session
router = APIRouter()
from fastapi.responses import JSONResponse

@router.post(
    "/register",
    tags=["User controller"]
)
def register(user: UserCreate, session: Session = Depends(get_session) ):
     
    create_info = create_user(user, session)
    auth_user = UserLogin(email =user.email, password= user.password )
    token_info = login_user(auth_user, session)
    
    return  JSONResponse(content= token_info ,status_code= 200)

@router.post(
    "/login",
    tags=["User controller"],
    status_code= 200
)
async def login(user:UserLogin, session: Session = Depends(get_session)):
    token_info= login_user(user, session)

    return  JSONResponse(content= token_info,status_code= 200)
    

@router.get('/getusers',  tags=["User controller"], status_code=200)
async def getusers( dependencies=Depends(JWTBearer()),session: Session = Depends(get_session)):
    users = session.query(User).all()
    return users


@router.post('/change-password',  tags=["User controller"], status_code=200)
async def password_change(user:ChangePassword, dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    change_info = await change_password(user, session)
    return  JSONResponse(content= change_info ,status_code= 200)


@router.post('/logout',  tags=["User controller"], status_code=200)
async def logout(dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    print("token:",dependencies)
    token = dependencies
    logout_info = await logout_user(token, session)
    return JSONResponse(content= logout_info, status_code=200, tags= ["User controller"])
@router.post("/get-user-information",response_model=UserInfo ,  tags= ["User controller"])
def get_user( access_token = Depends(JWTBearer()),session: Session = Depends(get_session)):
    user_info = get_user_info(access_token, session)
    return user_info

@router.post('/refresh', tags= ["User controller"] )
async def refresh(dependencies=Depends(JWTBearer())):
    return JSONResponse(
        content= {
            "access_token":dependencies
        },
        status_code= 200
    )

@router.post("/request_password_reset", tags= ["User controller"] )
def request_password_reset(req: ForgotPasswordRequest, session: Session = Depends(get_session)):
    email_status = reset_password_request(email= req.email, session=session)
    return JSONResponse(
        content= email_status,
        status_code= 200
    )

@router.post("/verify-code", tags= ["User controller"] )
def verify_reset_code(req: VerificationCodeRequest, dependencies = Depends(JWTBearer()), session:Session = Depends(get_session)):
    if not verify_forgot_code(dependencies,req.email, req.verify_code, session= session):
        raise HTTPException(status_code=400, detail="Invalid request")
    
    return {"message": "Verification code is valid"}
@router.post("/reset-password", tags= ["User controller"])
def password_reset(req:ResetPasswordRequest, dependencies = Depends(JWTBearer()), session: Session = Depends(get_session)):
    
    reset_info = reset_password(token= dependencies, email=req.email, new_password=req.new_password, session = session)
    return JSONResponse(
        content= reset_info,
        status_code= 200
    )