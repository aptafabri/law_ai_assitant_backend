from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from app import schemas


router = APIRouter()

@router.post(
    "/ingest",
    tags=["RagController"]
)
def ingestion_doc():
    """
    Ingest datasources for RAG such as pdf, txt, doc into Pinecone vectorestore.
    """
    return {"success":"true"}




@router.post(
    "/chat",
    tags=["RagController"]
)
def chat_with_document():
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """






