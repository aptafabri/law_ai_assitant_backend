from fastapi import APIRouter, Depends, Request, Body
from fastapi.responses import JSONResponse, Response
from typing import List
from sqlalchemy.orm import Session
from database.session import get_session
from crud.chat import (
    get_sessions_by_userid,
    get_messages_by_session_id,
    remove_session_summary,
    remove_messages_by_session_id,
    get_latest_messages_by_userid,
    upvote_chat_session,
    devote_chat_session,
    init_postgres_chat_memory,
    download_legal_description,
    delete_s3_bucket_folder,
    remove_sessions_by_user_id,
    check_shared_session_status,
    create_session_sharelink,
    get_shared_session_messages,
    get_shared_sessions_by_user_id,
    delete_shared_sessions_by_user_id,
    delete_shared_session_by_id,
    get_original_legal_case,
)
from crud.user import get_userid_by_token
from schemas.message import (
    SessionSummary,
    LegalMessage,
    SharedSessionSummary,
    CreateSharedLinkRequest,
    DisplaySharedSessionRequest,
    DeleteSharedSessionRequest,
    DisplaySharedSessionMessages,
)
from core.auth_bearer import JWTBearer
import urllib.parse

router = APIRouter()


@router.post(
    "/get-sessions-by-userid",
    tags=["ChatLegalController"],
    response_model=List[SessionSummary],
    status_code=200,
)
def get_sessions(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    sessions = get_sessions_by_userid(user_id, session)
    return sessions


@router.post(
    "/get-chathistory-by-sessionid",
    tags=["ChatLegalController"],
    response_model=List[LegalMessage],
    status_code=200,
)
def get_chat_history(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
) -> List[LegalMessage]:
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    chat_history = get_messages_by_session_id(
        user_id=user_id, session_id=session_id, session=session
    )
    return chat_history


@router.post("/remove-session", tags=["ChatLegalController"], status_code=200)
async def delete_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    remove_session_summary(session_id=session_id, session=session)
    delete_s3_bucket_folder(user_id=user_id, session_id=session_id)
    remove_info = remove_messages_by_session_id(
        user_id=user_id, session_id=session_id, session=session
    )
    session_memory = init_postgres_chat_memory(session_id=session_id)
    session_memory.clear()
    return JSONResponse(content=remove_info, status_code=200)


@router.post(
    "/get-latest-session",
    tags=["ChatLegalController"],
    response_model=List[LegalMessage],
    status_code=200,
)
def get_latest_session(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    latest_session_messages = get_latest_messages_by_userid(user_id, session)
    return latest_session_messages


@router.post("/upvote-chat-session", tags=["ChatLegalController"], status_code=200)
def upvote_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    updated_status = upvote_chat_session(
        session_id=session_id, user_id=user_id, session=session
    )
    return JSONResponse(content=updated_status, status_code=200)


@router.post("/devote-chat-session", tags=["ChatLegalController"], status_code=200)
def devote_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body["session_id"]
    user_id = get_userid_by_token(dependencies)
    updated_status = devote_chat_session(
        session_id=session_id, user_id=user_id, session=session
    )
    return JSONResponse(content=updated_status, status_code=200)


@router.get("/download-legal-pdf", tags=["ChatLegalController"], status_code=200)
def download_pdf(
    session_id: str = None,
    legal_s3_key: str = None,
    legal_file_name: str = None,
    dependencies=Depends(JWTBearer()),
):
    user_id = get_userid_by_token(dependencies)
    data = download_legal_description(
        user_id=user_id, session_id=session_id, legal_s3_key=legal_s3_key
    )
    encoded_filename = urllib.parse.quote(legal_file_name)
    print("encoded file_name:", encoded_filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return Response(data["Body"].read(), media_type="application/pdf", headers=headers)


@router.post("/remove-all-sessions", tags=["ChatLegalController"], status_code=200)
def remove_all_session(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    if remove_sessions_by_user_id(user_id=user_id, db_session=session) == True:
        return JSONResponse(
            content={"Success": True, "message": "Deleted all sessions."},
            status_code=200,
        )
    else:
        return JSONResponse(
            content={"Success": False, "message": " Internal Server Error."},
            status_code=500,
        )


@router.post("/check-shared-session", tags=["ChatController"])
def check_shared_session(
    request: CreateSharedLinkRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    user_id = get_userid_by_token(dependencies)
    session_id = request.session_id
    is_shared, is_updatable, shared_id = check_shared_session_status(
        user_id=user_id, session_id=session_id, db_session=session
    )
    return JSONResponse(
        content={
            "is_shared": is_shared,
            "updatable": is_updatable,
            "shared_id": shared_id,
        }
    )


@router.post("/create-share-link", tags=["ChatController"])
def create_share_link(
    request: CreateSharedLinkRequest,
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    user_id = get_userid_by_token(dependencies)
    session_id = request.session_id
    shared_url = create_session_sharelink(
        user_id=user_id, session_id=session_id, db_session=session
    )
    print(shared_url)
    return JSONResponse(
        content={"Success": True, "shared_link": shared_url}, status_code=200
    )


@router.post(
    "/display-shared-session",
    tags=["ChatController"],
    response_model=DisplaySharedSessionMessages,
)
def display_shared_session(
    request: DisplaySharedSessionRequest, session: Session = Depends(get_session)
):
    shared_id = request.shared_id
    session_summary, session_messages, shared_date = get_shared_session_messages(
        shared_id=shared_id, db_session=session
    )
    messages = [
        LegalMessage(
            content=msg.content,
            role=msg.role,
            legal_attached=msg.legal_attached,
            legal_file_name=msg.legal_file_name,
            legal_s3_key=msg.legal_s3_key,
        )
        for msg in session_messages
    ]
    shared_session = DisplaySharedSessionMessages(
        summary=session_summary, shared_date=shared_date, messages=messages
    )

    return shared_session


@router.post("/get-shared-links", tags=["ChatController"])
def get_all_shared_sessions(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
) -> List[SharedSessionSummary]:
    user_id = get_userid_by_token(token)
    shared_sessions = get_shared_sessions_by_user_id(
        user_id=user_id, db_session=session
    )
    return shared_sessions


@router.post("/delete-all-shared-sessions", tags=["ChatController"])
def delete_all_shared_sessions(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(token)
    deleted_status = delete_shared_sessions_by_user_id(user_id, session)
    return JSONResponse(
        content={"Success": deleted_status, "messages": "Deleted all shared links."},
        status_code=200,
    )


@router.post("/delete-shared-session", tags=["ChatController"])
def delete_shared_session(
    request: DeleteSharedSessionRequest,
    token=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    user_id = get_userid_by_token(token)
    session_id = request.session_id
    deleted_status = delete_shared_session_by_id(
        user_id=user_id, session_id=session_id, db_session=session
    )
    return JSONResponse(
        content={"Success": deleted_status, "messages": "Deleted shared link."},
        status_code=200,
    )


@router.get("/get-legalcase", tags=["ChatController"])
def get_original_legalcase(
    case_id: str,
    type: str,
    # token=Depends(JWTBearer()),
):
    data = get_original_legal_case(case_id=case_id, data_type=type)
    if type == "pdf":
        return Response(
            content=data["Body"].read(), media_type="application/pdf", status_code=200
        )
    else:
        return Response(
            content=data["Body"].read(), media_type="plain/text", status_code=200
        )
