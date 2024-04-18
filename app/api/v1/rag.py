from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from crud.rag import run_llm_conversational_retrievalchain_with_sourcelink, run_llm_conversational_retrievalchain_without_sourcelink
from crud.chat import add_message, summarize_session, add_session_summary, session_exist
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
def chat_with_document(message:ChatRequest, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    
    # response = run_llm_conversational_retrievalchain_with_sourcelink(question=message.question, session_id= message.session_id)
    response = run_llm_conversational_retrievalchain_without_sourcelink(question=message.question, session_id= message.session_id)

    print("response", response)
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    user_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= message.question, role = "user", created_date=created_date)
    ai_message = ChatAdd( user_id = user_id, session_id= message.session_id, content= response["answer"], role = "assistant", created_date= created_date)
    
    add_message(user_message, session)
    add_message(ai_message, session)
    
    print(session_exist(session_id=message.session_id, session= session))
    if(session_exist(session_id=message.session_id, session= session)==True):
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"]
            },
            status_code= 200
        )
    else:
        summary = summarize_session(question=message.question, answer= response["answer"])
        add_session_summary(user_id=user_id, session_id= message.session_id, summary= summary, session=session)
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": message.session_id,
                "question":message.question,
                "answer":response["answer"],
                "title":summary
            },
            status_code= 200
        )

       
@router.post("/chat-test")
def rag_test(message:ChatRequest):
    response = run_llm_conversational_retrievalchain_without_sourcelink(question=message.question, session_id= message.session_id)
    return response

    






