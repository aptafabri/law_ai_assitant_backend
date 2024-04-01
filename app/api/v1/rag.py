from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from crud.rag import run_llm_conversational_retrievalchain_with_sourcelink
from crud.chat import add_message
from crud.user import get_userid_by_token
from database.session import get_session
from schemas.message import ChatRequest, ChatAdd
from datetime import datetime
from core.auth_bearer import JWTBearer
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
    tags=["RagController"],
    status_code= 200
)
async def chat_with_document(message:ChatRequest, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    
    response = await run_llm_conversational_retrievalchain_with_sourcelink(question=message.question, session_id= message.session_id)
    user_id = await get_userid_by_token(dependencies)
    created_date = datetime.now()
    user_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= message.question, role = "Human", created_date=created_date)
    ai_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= response["answer"], role = "AI", created_date= created_date)
    
    add_message(user_message, session)
    add_message(ai_message, session)
    
       
    return {
        "user_id": user_id,
        "session_id": message.session_id,
        "question":message.question,
        "answer":response["answer"]
    }
    
    






