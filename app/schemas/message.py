from pydantic import BaseModel
from datetime import datetime

class ChatRequestWithOutUserID(BaseModel):
  
    session_id: str
    question: str

class ChatRequest(BaseModel):
    user_id: int
    session_id: str
    question: str
    
class ChatAdd(BaseModel):
    user_id: int
    session_id: str
    content: str
    role: str
    created_date: datetime

class SessionSummary(BaseModel):
    session_id: str
    name: str
    summary: str

class Message(BaseModel):
    id: int
    content: str
    role: str
    created_date: datetime