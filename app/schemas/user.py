from pydantic import BaseModel
import datetime

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email:str
    password:str
        

class ChangePassword(BaseModel):
    email:str
    old_password:str
    new_password:str

