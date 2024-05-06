from fastapi import APIRouter, Depends, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from typing import  List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat_legal import get_sessions_by_userid, get_messages_by_session_id, remove_session_summary, remove_messages_by_session_id, get_latest_messages_by_userid, upvote_chat_session, devote_chat_session, init_postgres_legal_chat_memory, download_legal_description, delete_s3_bucket_folder
from crud.user import get_userid_by_token
from schemas.message import SessionSummary, Message, SessionSummaryRequest, DownloadLegalPdf, LegalMessage
from core.auth_bearer import JWTBearer
from langchain_community.chat_message_histories.postgres import PostgresChatMessageHistory
from core.config import settings
import urllib.parse

router = APIRouter()

@router.post("/get-sessions-by-userid", tags= ["ChatLegalController"], response_model= List[SessionSummary], status_code=200)
def get_sessions(dependencies=Depends(JWTBearer()), session:Session = Depends(get_session)):
    user_id = get_userid_by_token(dependencies)
    sessions = get_sessions_by_userid(user_id, session)
    return sessions

@router.post("/get-chathistory-by-sessionid", tags=['ChatLegalController'], response_model=List[LegalMessage], status_code=200)
def get_chat_history(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id =  get_userid_by_token(dependencies)
    chat_history = get_messages_by_session_id(user_id= user_id,session_id=session_id, session=session)
    return chat_history

@router.post("/remove-session", tags=['ChatLegalController'], status_code=200)
async def delete_session(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    remove_session_summary(session_id= session_id, session= session)
    delete_s3_bucket_folder(user_id= user_id, session_id= session_id)
    remove_info = remove_messages_by_session_id(user_id= user_id,session_id=session_id, session=session) 
    session_memory = init_postgres_legal_chat_memory(session_id = session_id)
    session_memory.clear()
    return JSONResponse(content= remove_info, status_code=200)

@router.post("/get-latest-session", tags=['ChatLegalController'], response_model=List[LegalMessage], status_code=200)
def get_latest_session(dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    user_id = get_userid_by_token(dependencies)
    latest_session_messages = get_latest_messages_by_userid(user_id, session)
    
    return latest_session_messages

@router.post("/upvote-chat-session", tags=['ChatLegalController'], status_code=200)
def upvote_session(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    updated_status = upvote_chat_session(session_id= session_id, user_id= user_id, session= session)
    return JSONResponse(content= updated_status, status_code=200)
 
@router.post("/devote-chat-session", tags=['ChatLegalController'], status_code=200)
def devote_session(body:dict = Body(), dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    updated_status = devote_chat_session(session_id= session_id, user_id= user_id, session= session)
    return JSONResponse(content= updated_status, status_code=200)

@router.get("/download-legal-pdf", tags=['ChatLegalController'], status_code=200 )
def download_pdf(session_id:str = None, legal_s3_key: str = None, legal_file_name: str = None, dependencies = Depends(JWTBearer())):
    user_id= get_userid_by_token(dependencies)
    # user_id = 2
    # session_id = "3565c5cd-63ef-42dc-859e-938b6f3269a6"
    # legal_file_name = "Profile.pdf"
    # legal_s3_key = "1714729956.563352_Profile.pdf"
    data = download_legal_description(user_id = user_id, session_id= session_id, legal_s3_key= legal_s3_key)
    encoded_filename = urllib.parse.quote(legal_file_name)
    print("encoded file_name:", encoded_filename)
    
    headers = {
        'Content-Disposition': f'attachment; filename*=UTF-8\'\'{encoded_filename}'
    }
    return StreamingResponse(content=data["Body"].iter_chunks(), headers=headers, media_type='application/pdf')
    # return Response(
    #     data["Body"].read(),
    #     media_type = 'application/pdf',
    #     headers = headers            
    # )