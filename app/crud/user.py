from models import User, TokenTable
from database.session import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserLogin, ChangePassword, UserInfo
from fastapi import Depends, Response, HTTPException
from fastapi.responses import JSONResponse
from core.utils import get_hashed_password, verify_password, create_access_token, create_refresh_token
from datetime import datetime, timezone, timedelta
import jwt
from core import settings
import secrets
from crud.notify import send_reset_password_mail
import asyncio
from core.utils import create_access_token
def create_user(user:UserCreate, session: Session):
    
    existing_user = session.query(User).filter_by(email=user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Eamil already registered")
    
    encrypted_password =get_hashed_password(user.password)
    
    new_user = User(username=user.username, email=user.email, password=encrypted_password )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return { "message":"user created successfully" }

def login_user(auth: UserLogin, session:Session):
    user = session.query(User).filter(User.email == auth.email).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Incorrect Email")

    hashed_pass = user.password
   
    if not verify_password(auth.password, hashed_pass):
        raise HTTPException(status_code=400, detail="Incorrect Password")
    
    access=create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    print(access, refresh)
    token_db = TokenTable(user_id=user.id,  access_token=access,  refresh_token=refresh, status=True)
    session.add(token_db)
    session.commit()
    session.refresh(token_db)
    token_info={
        "access_token": access,
        "refresh_token": refresh,
    }
    return token_info
   

async def change_password(req:ChangePassword, session:Session):
    
    update_user = session.query(User).filter(User.email == req.email).first()
    if update_user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    
    if not verify_password(req.old_password, update_user.password):
        raise HTTPException(status_code=400, detail="Incorrect Password.")

    
    encrypted_password = get_hashed_password(req.new_password)
    update_user.password = encrypted_password
    session.commit()
    
    return {"message": "Password changed successfully"}

async def logout_user(token:str, session:Session):
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    user_id = payload['sub']
    
    token_record = session.query(TokenTable).all()
    info=[]
    for record in token_record :
        print("record",record)
        print((datetime.now() - record.created_date).days)
        
        if (datetime.now() - record.created_date).days >1:
            info.append(record.user_id)
    
    """
        This loop iterates through each token record and checks if its creation date is older than one day. If so, it appends the corresponding user ID to the info list.
    """
    if info:
        existing_token = session.query(TokenTable).where(TokenTable.user_id.in_(info)).delete()
        session.commit()
        
    existing_token = session.query(TokenTable).filter(TokenTable.user_id == user_id, TokenTable.access_token==token).first()
    if existing_token:
        existing_token.status=False
        session.add(existing_token)
        session.commit()
        session.refresh(existing_token)
    return {"message":"Logout Successfully"} 

def get_userid_by_token(token:str)-> int:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    user_id = payload['sub']
    return user_id

def get_user_info(token:str, session: Session):
    
    user_id = get_userid_by_token(token)
    try:
        user_record = session.query(User.email, User.username).filter(User.id == user_id).first()
        
        if user_record:
            user_info= UserInfo(email= user_record[0], user_name=user_record[1])
            return user_info
        else:
            raise HTTPException(status_code=400, detail="User not found.")

    except Exception as e:
        print("An error occurred while querying the database:", str(e))
        return []

async def generate_verification_code():
    return secrets.token_hex(3)

def reset_password_request(email:str, session: Session):
    update_user = session.query(User).filter(User.email == email).first()
    if update_user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    verify_code = generate_verification_code()
    print(verify_code, type(verify_code))
    update_user.verify_code = verify_code
    update_user.verify_code_expiry = datetime.now() + timedelta(minutes= 5)
    session.commit()

    send_reset_password_mail(recipient_email= update_user.email, user_name=update_user.username, verify_code=verify_code)
    access_token = create_access_token(update_user.id)
    return {
        "message":"Password reset code sent.",
        "access_token":access_token    
    }

def verify_forgot_code(token:str, email: str, code: str, session: Session):
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id == user_id, User.email == email).first()
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")
    
    if user.verify_code == code:
        if user.verify_code_expiry > datetime.now():
            user.reset_verified = True
            session.commit()
            return True
    return False

def reset_password(token: str, email:str, new_password:str,  session:Session):
    user_id = get_userid_by_token(token)
    user = session.query(User).filter(User.id ==user_id,User.email == email).first()
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
    
    return {"message": "Password reseted successfully"}

