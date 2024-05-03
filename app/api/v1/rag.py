from fastapi import APIRouter, Depends, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from crud.rag import rag_general_chat, rag_legal_chat, rag_test_chat , get_relevant_legal_cases
from crud.chat_general import add_message, summarize_session, add_session_summary, session_exist
from crud.chat_legal import add_legal_message, add_legal_chat_message, add_legal_session_summary, legal_session_exist, read_pdf, upload_legal_description, generate_question
from crud.user import get_userid_by_token
from database.session import get_session
from schemas.message import ChatRequest, ChatAdd, LegalChatAdd
from datetime import datetime
from core.auth_bearer import JWTBearer
router = APIRouter()

@router.post(
    "/chat",
    tags=["RagController"],
    status_code= 200
)
def chat_with_document(message:ChatRequest, dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)):
    """
    Chat with doc in Vectore Store using similarity search and OpenAI embedding.
    """
    response = rag_general_chat(question=message.question, session_id= message.session_id)
    #response = run_llm_conversational_retrievalchain_without_sourcelink(question=message.question, session_id= message.session_id)

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
                "answer":response["answer"],
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
                "title":summary,
            },
            status_code= 200
        )

@router.post('/chat-legal', tags = ['RagController'], status_code = 200 )
async def chat_with_legal(session_id:str = Form(), question:str= Form(), file:UploadFile = File(...), dependencies = Depends(JWTBearer()),  session: Session = Depends(get_session)):
    legal_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()

    pdf_contents = await file.read()
    if pdf_contents:
        attached_pdf = True
        file_name = file.filename 
        time_stamp = created_date.timestamp()
        legal_s3_key = f"{time_stamp}_{file_name}"
        upload_legal_description(file_content=pdf_contents, user_id = user_id, session_id= session_id, legal_s3_key= legal_s3_key)
        legal_question = read_pdf(pdf_contents)
    total_question = legal_question +  question
    response = rag_legal_chat(question=total_question, session_id= session_id)
    answer = response["answer"]
    user_message = LegalChatAdd(
        user_id= user_id,
        session_id= session_id,
        content=question,
        role= 'user',
        legal_attached=attached_pdf,
        legal_file_name=file_name,
        legal_s3_key= legal_s3_key,
        created_date = created_date
    )
    ai_message = LegalChatAdd(
        user_id= user_id,
        session_id= session_id,
        content= answer,
        role= 'assistant',
        legal_attached=False,
        legal_file_name='',
        legal_s3_key= '',
        created_date = created_date
    )
    add_legal_chat_message(user_message, session)
    add_legal_chat_message(ai_message, session)
    if(legal_session_exist(session_id=session_id, session= session)==True):
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "legal_attached": attached_pdf,
                "legal_file_name":file_name,
                "legal_s3_key":legal_s3_key,
                "answer":answer,
            },
            status_code= 200
        )
    else:
        summary = summarize_session(question=total_question, answer= answer)
        add_legal_session_summary(user_id=user_id, session_id= session_id, summary= summary, session=session)
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "legal_attached": attached_pdf,
                "legal_file_name":file_name,
                "legal_s3_key":legal_s3_key,
                "answer":answer,
                "title":summary,
            },
            status_code= 200
        )

@router.post('/get-legal-cases', tags= ['RagController'])
def  get_legal_cases(body:dict = Body(), dependencies=Depends(JWTBearer())):
    session_id = body["session_id"]
    legal_cases = get_relevant_legal_cases(session_id= session_id)
    return JSONResponse(
            content={
                "session_id": session_id,
                "legal_cases": legal_cases
            },
            status_code= 200
        )

@router.post("/chat-test")
async def rag_test(session_id:str = Form(), question:str= Form(), file:UploadFile = File(...), dependencies = Depends(JWTBearer()),  session: Session = Depends(get_session)):
    standalone_question = ""
    legal_s3_key = ""
    file_name = ""
    attached_pdf = False
    user_id = get_userid_by_token(dependencies)
    created_date = datetime.now()
    pdf_contents = await file.read()
    if pdf_contents:
        attached_pdf = True
        file_name = file.filename 
        time_stamp = created_date.timestamp()
        legal_s3_key = f"{time_stamp}_{file_name}"
        upload_legal_description(file_content=pdf_contents, user_id = user_id, session_id= session_id, legal_s3_key= legal_s3_key)
        pdf_contents = read_pdf(pdf_contents)
        standalone_question = generate_question(pdf_contents=pdf_contents, question= question)
    else :
        standalone_question = question
    response = rag_legal_chat(question=standalone_question, session_id= session_id)
    answer = response["answer"]
    # answer = "My name is AdaletGPT."
    user_message = LegalChatAdd(
        user_id= user_id,
        session_id= session_id,
        content=question,
        role= 'user',
        legal_attached=attached_pdf,
        legal_file_name=file_name,
        legal_s3_key= legal_s3_key,
        created_date = created_date
    )
    ai_message = LegalChatAdd(
        user_id= user_id,
        session_id= session_id,
        content= answer,
        role= 'assistant',
        legal_attached=False,
        legal_file_name='',
        legal_s3_key= '',
        created_date = created_date
    )
    add_legal_chat_message(user_message, session)
    add_legal_chat_message(ai_message, session)

    print("total-question:", standalone_question)
    if(legal_session_exist(session_id=session_id, session= session)==True):
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "answer":answer,
            },
            status_code= 200
        )
    else:
        summary = summarize_session(question=standalone_question, answer= answer)
        add_legal_session_summary(user_id=user_id, session_id= session_id, summary= summary, session=session)
        return JSONResponse(
            content={
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "answer":answer,
                "title":summary,
            },
            status_code= 200
        )

    return {"ocr_text":total_question}
    # response = rag_test_chat(question=message.question, session_id= message.session_id)
    
    # return response
    






