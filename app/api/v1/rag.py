from fastapi import APIRouter, Depends, HTTPException, status, Request
from crud.rag import run_llm_conversational_retrievalchain, run_llm_conversational_retrievalchain_with_sourcelink
from schemas.message import ChatRequest

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
async def chat_with_document(message:ChatRequest):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
   
    response = run_llm_conversational_retrievalchain_with_sourcelink(question=message.question, session_id= message.session_id)

    
    return {
        "session_id": message.session_id,
        "question":response["question"],
        "answer":response["answer"],
        "chat_history":response["chat_history"]
    }
    
    






