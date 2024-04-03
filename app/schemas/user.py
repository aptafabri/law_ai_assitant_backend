from pydantic import BaseModel, EmailStr
import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email:EmailStr
    password:str
        

class ChangePassword(BaseModel):
    email:EmailStr
    old_password:str
    new_password:str

