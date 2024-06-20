from pydantic import BaseModel
from datetime import datetime
from typing import List, Any


class ChatRequest(BaseModel):
    session_id: str
    question: str


class ChatAdd(BaseModel):
    user_id: int
    session_id: str
    content: str
    role: str
    created_date: datetime


class LegalChatAdd(BaseModel):
    user_id: int
    session_id: str
    content: str
    role: str
    legal_file_name: str
    legal_s3_key: str
    legal_attached: bool
    created_date: datetime


class SessionSummary(BaseModel):
    user_id: int
    session_id: str
    summary: str
    created_date: datetime
    is_favourite: bool
    favourite_date: datetime


class Message(BaseModel):
    content: str
    role: str


class LegalMessage(BaseModel):
    content: str
    role: str
    legal_attached: bool
    legal_file_name: str
    legal_s3_key: str


class DisplaySharedSessionMessages(BaseModel):
    summary: str
    shared_date: datetime
    messages: List[LegalMessage]


class SessionSummaryRequest(BaseModel):
    session_id: str
    question: str
    answer: str


class DownloadLegalPdf(BaseModel):
    session_id: str
    legal_s3_key: str
    legal_file_name: str


class CreateSharedLinkRequest(BaseModel):
    session_id: str


class DisplaySharedSessionRequest(BaseModel):
    shared_id: str


class SharedSessionSummary(BaseModel):
    session_id: str
    summary: str
    shared_id: str
    shared_date: datetime


class DeleteSharedSessionRequest(BaseModel):
    session_id: str
