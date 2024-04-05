from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from crud.user import create_user, login_user, change_password, logout_user, get_user_info
from schemas.user import UserCreate, UserLogin, ChangePassword, UserInfo
from core.auth_bearer import JWTBearer
from models import User
from database.session import get_session
router = APIRouter()
from fastapi.responses import JSONResponse

@router.post(
    "/register",
    tags=["User controller"]
)
async def register(user: UserCreate, session: Session = Depends(get_session) ):
     
    create_info = await create_user(user, session)
    return  JSONResponse(content= create_info ,status_code= 200)

@router.post(
    "/login",
    tags=["User controller"],
    status_code= 200
)
async def login(user:UserLogin, session: Session = Depends(get_session)):
    token_info= await login_user(user, session)
    return  JSONResponse(content= token_info,status_code= 200)
    

@router.get('/getusers')
async def getusers( dependencies=Depends(JWTBearer()),session: Session = Depends(get_session)):
    user = session.query(User).all()
    return user


@router.post('/change-password')
async def password_change(user:ChangePassword, dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    change_info = await change_password(user, session)
    return  JSONResponse(content= change_info ,status_code= 200)


@router.post('/logout')
async def logout(dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    print("token:",dependencies)
    token = dependencies
    logout_info = await logout_user(token, session)
    return JSONResponse(content= logout_info, status_code=200)
@router.post("/get-user-information",response_model=UserInfo)
def get_user( access_token = Depends(JWTBearer()),session: Session = Depends(get_session)):
    user_info = get_user_info(access_token, session)
    return user_info

@router.post('/refresh')
async def refresh(dependencies=Depends(JWTBearer())):
    return JSONResponse(
        content= {
            "access_token":dependencies
        },
        status_code= 200
    )
   