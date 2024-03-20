from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.crud.rag import run_llm_conversational_retrievalchain


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
async def chat_with_document(request:Request):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    data= await request.json()
    question = data["question"] 
    answer = run_llm_conversational_retrievalchain(question=question, chat_history=[])
    
    return {"answer":answer}
    






