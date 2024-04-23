from fastapi import APIRouter
from api.v1 import user
from api.v1 import rag
from api.v1 import chat_general
from api.v1 import chat_legal
from initialiser import init

init()

api_router = APIRouter()

api_router.include_router(rag.router, prefix='/rag')
api_router.include_router(user.router, prefix='/user')
api_router.include_router(chat_general.router, prefix='/chat')
api_router.include_router(chat_legal.router, prefix='/chat-legal')
