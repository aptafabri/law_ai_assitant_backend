from fastapi import APIRouter
from api.v1 import user, chat
from app.api.v1 import rag_general
from initialiser import init

init()

api_router = APIRouter()

api_router.include_router(rag_general.router, prefix='/rag')
api_router.include_router(user.router, prefix='/user')
api_router.include_router(chat.router, prefix='/chat')
