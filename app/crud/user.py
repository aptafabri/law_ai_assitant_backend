from models import User, TokenTable
from database.session import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserLogin, ChangePassword
from fastapi import Depends, Response, HTTPException
from fastapi.responses import JSONResponse
from core.utils import get_hashed_password, verify_password, create_access_token, create_refresh_token
from datetime import datetime, timezone
import jwt
from core import settings


async def create_user(user:UserCreate, session: Session):
    
    existing_user = session.query(User).filter_by(email=user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Eamil already registered")
    
    encrypted_password =get_hashed_password(user.password)
    
    new_user = User(username=user.username, email=user.email, password=encrypted_password )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return { "message":"user created successfully" }

async def login_user(auth: UserLogin, session:Session):
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
   

async def change_password(user:ChangePassword, session:Session):
    
    update_user = session.query(User).filter(User.email == user.email).first()
    if create_user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    
    if not verify_password(user.old_password, update_user.password):
        raise HTTPException(status_code=400, detail="Incorrect Password.")

    
    encrypted_password = get_hashed_password(user.new_password)
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

async def get_userid_by_token(token:str)-> int:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    user_id = payload['sub']
    return user_id
    