from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    session_id: str
    question: str

    
class ChatAdd(BaseModel):
    user_id: int
    session_id: str
    content: str
    role: str
    created_date: datetime

class SessionSummary(BaseModel):
    user_id:int
    session_id: str
    summary: str
    created_date: datetime
    is_favourite: bool
    favourite_date: datetime

class Message(BaseModel):
    content: str
    role: str
    
class SessionSummaryRequest(BaseModel):
    session_id:str
    question:str
    answer:str
   