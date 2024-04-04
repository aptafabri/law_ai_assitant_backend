from pydantic import BaseModel
from datetime import datetime
from typing import List


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
    session_id: str
    name: str
    summary: str

class SessionSummaryResponse(BaseModel):
    sessions:List[SessionSummary]
    access_token:str

class Message(BaseModel):
    content: str
    role: str
    
class ChatHistoryResponse(BaseModel):
    chat_history:List[Message]
    access_token:str
   