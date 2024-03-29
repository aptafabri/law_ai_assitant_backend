from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status, Request
from crud.user import create_user, get_session, login_user, change_password, logout_user
from schemas.user import UserCreate, UserLogin, ChangePassword
from core.auth_bearer import JWTBearer
from models import User
router = APIRouter()


@router.post(
    "/register",
    tags=["User controller"]
)
async def register(user: UserCreate, session: Session = Depends(get_session) ):
     
    return create_user(user, session)

@router.post(
    "/login",
    tags=["User controller"]
)
async def login(user:UserLogin, session: Session = Depends(get_session)):
       
    return login_user(user, session)

@router.get('/getusers')
async def getusers( dependencies=Depends(JWTBearer()),session: Session = Depends(get_session)):
    user = session.query(User).all()
    return user


@router.post('/change-password')
async def password_change(user:ChangePassword, dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    return change_password(user, session)


@router.post('/logout')
async def logout(dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    token = dependencies
    return logout_user(token, session)
    