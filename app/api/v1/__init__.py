from fastapi import APIRouter
from api.v1 import rag, user
from initialiser import init

init()

api_router = APIRouter()

api_router.include_router(rag.router, prefix='/rag')
api_router.include_router(user.router, prefix='/user')