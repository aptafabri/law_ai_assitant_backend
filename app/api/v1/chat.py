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
    archive_session,
    get_archived_sessions_by_user_id,
    delete_archived_session_by_id,
    delete_archived_sessions_by_user_id,
    archive_all_session,
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
    GetOriginalLegalCaseRequest,
    ArchiveChatRequest,
    ArchivedSessionSummary,
)
from core.auth_bearer import JWTBearer
import urllib.parse
from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)

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
    logger.debug("Fetching sessions for user_id: %s", user_id)
    sessions = get_sessions_by_userid(user_id, session)
    logger.info("Retrieved %d sessions for user_id: %s", len(sessions), user_id)
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
    session_id = body.get("session_id")
    user_id = get_userid_by_token(dependencies)
    logger.debug("Fetching chat history for session_id: %s, user_id: %s", session_id, user_id)
    chat_history = get_messages_by_session_id(
        user_id=user_id, session_id=session_id, session=session
    )
    logger.info("Retrieved %d messages for session_id: %s", len(chat_history), session_id)
    return chat_history


@router.post("/remove-session", tags=["ChatLegalController"], status_code=200)
async def delete_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body.get("session_id")
    user_id = get_userid_by_token(dependencies)
    logger.debug("Removing session summary for session_id: %s", session_id)
    remove_session_summary(session_id=session_id, session=session)
    logger.debug("Deleting S3 bucket folder for user_id: %s, session_id: %s", user_id, session_id)
    delete_s3_bucket_folder(user_id=user_id, session_id=session_id)
    logger.debug("Removing messages for session_id: %s", session_id)
    remove_info = remove_messages_by_session_id(
        user_id=user_id, session_id=session_id, session=session
    )
    logger.debug("Initializing PostgreSQL chat memory for session_id: %s", session_id)
    session_memory = init_postgres_chat_memory(session_id=session_id)
    session_memory.clear()
    logger.info("Session removed successfully for session_id: %s", session_id)
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
    logger.debug("Fetching latest session messages for user_id: %s", user_id)
    latest_session_messages = get_latest_messages_by_userid(user_id, session)
    logger.info("Retrieved latest session messages for user_id: %s", user_id)
    return latest_session_messages


@router.post("/upvote-chat-session", tags=["ChatLegalController"], status_code=200)
def upvote_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body.get("session_id")
    user_id = get_userid_by_token(dependencies)
    logger.debug("Upvoting session_id: %s for user_id: %s", session_id, user_id)
    updated_status = upvote_chat_session(
        session_id=session_id, user_id=user_id, session=session
    )
    logger.info("Session upvoted successfully for session_id: %s", session_id)
    return JSONResponse(content=updated_status, status_code=200)


@router.post("/devote-chat-session", tags=["ChatLegalController"], status_code=200)
def devote_session(
    body: dict = Body(),
    dependencies=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    session_id = body.get("session_id")
    user_id = get_userid_by_token(dependencies)
    logger.debug("Devoting session_id: %s for user_id: %s", session_id, user_id)
    updated_status = devote_chat_session(
        session_id=session_id, user_id=user_id, session=session
    )
    logger.info("Session devoted successfully for session_id: %s", session_id)
    return JSONResponse(content=updated_status, status_code=200)


@router.get("/download-legal-pdf", tags=["ChatLegalController"], status_code=200)
def download_pdf(
    session_id: str = None,
    legal_s3_key: str = None,
    legal_file_name: str = None,
    dependencies=Depends(JWTBearer()),
):
    user_id = get_userid_by_token(dependencies)
    logger.debug("Downloading legal PDF for user_id: %s, session_id: %s", user_id, session_id)
    data = download_legal_description(
        user_id=user_id, session_id=session_id, legal_s3_key=legal_s3_key
    )
    encoded_filename = urllib.parse.quote(legal_file_name)
    logger.info("Encoded filename: %s", encoded_filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    logger.info("Legal PDF downloaded successfully for session_id: %s", session_id)
    return Response(data["Body"].read(), media_type="application/pdf", headers=headers)


@router.post("/remove-all-sessions", tags=["ChatLegalController"], status_code=200)
def remove_all_session(
    dependencies=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(dependencies)
    logger.debug("Removing all sessions for user_id: %s", user_id)
    try:
        result = remove_sessions_by_user_id(user_id=user_id, db_session=session)
        if result:
            logger.info("All sessions deleted successfully for user_id: %s", user_id)
            return JSONResponse(
                content={"Success": True, "message": "Deleted all sessions."},
                status_code=200,
            )
        else:
            logger.error("Failed to delete all sessions for user_id: %s", user_id)
            return JSONResponse(
                content={"Success": False, "message": "Internal Server Error."},
                status_code=500,
            )
    except Exception as e:
        logger.exception("Exception occurred while deleting all sessions: %s", str(e))
        return JSONResponse(
            content={"Success": False, "message": "Internal Server Error."},
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
    logger.debug("Checking shared session status for session_id: %s, user_id: %s", session_id, user_id)
    is_shared, is_updatable, shared_id = check_shared_session_status(
        user_id=user_id, session_id=session_id, db_session=session
    )
    logger.info("Shared session status retrieved for session_id: %s", session_id)
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
    logger.debug("Creating share link for session_id: %s, user_id: %s", session_id, user_id)
    shared_url = create_session_sharelink(
        user_id=user_id, session_id=session_id, db_session=session
    )
    logger.info("Share link created: %s", shared_url)
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
    logger.debug("Displaying shared session for shared_id: %s", shared_id)
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
    logger.info("Shared session displayed for shared_id: %s", shared_id)
    return shared_session


@router.post("/get-shared-links", tags=["ChatController"])
def get_all_shared_sessions(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
) -> List[SharedSessionSummary]:
    user_id = get_userid_by_token(token)
    logger.debug("Fetching all shared sessions for user_id: %s", user_id)
    shared_sessions = get_shared_sessions_by_user_id(
        user_id=user_id, db_session=session
    )
    logger.info("Retrieved %d shared sessions for user_id: %s", len(shared_sessions), user_id)
    return shared_sessions


@router.post("/delete-all-shared-sessions", tags=["ChatController"])
def delete_all_shared_sessions(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(token)
    logger.debug("Deleting all shared sessions for user_id: %s", user_id)
    deleted_status = delete_shared_sessions_by_user_id(user_id, session)
    if deleted_status:
        logger.info("All shared sessions deleted for user_id: %s", user_id)
    else:
        logger.warning("Failed to delete all shared sessions for user_id: %s", user_id)
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
    logger.debug("Deleting shared session for session_id: %s, user_id: %s", session_id, user_id)
    deleted_status = delete_shared_session_by_id(
        user_id=user_id, session_id=session_id, db_session=session
    )
    if deleted_status:
        logger.info("Shared session deleted for session_id: %s", session_id)
    else:
        logger.warning("Failed to delete shared session for session_id: %s", session_id)
    return JSONResponse(
        content={"Success": deleted_status, "messages": "Deleted shared link."},
        status_code=200,
    )


@router.post("/get-legalcase", tags=["ChatController"])
def get_original_legalcase(
    request: GetOriginalLegalCaseRequest,
    token=Depends(JWTBearer()),
):
    case_id = request.case_id
    data_type = request.datatype
    logger.debug("Fetching original legal case for case_id: %s, data_type: %s", case_id, data_type)
    try:
        data = get_original_legal_case(case_id=case_id, data_type=data_type)
        if data_type == "pdf":
            logger.info("Original legal case PDF retrieved for case_id: %s", case_id)
            return Response(
                content=data["Body"].read(),
                media_type="application/pdf",
                status_code=200,
                headers={"Content-Type": "application/pdf; charset=UTF-8"},
            )
        elif data_type == "txt":
            legal_txt = data["Body"].read().decode("utf-8")
            logger.info("Original legal case text retrieved for case_id: %s", case_id)
            return JSONResponse(
                content={"content": legal_txt},
                status_code=200,
                headers={"Content-Type": "application/json"},
            )
        else:
            logger.error("Invalid data_type provided: %s", data_type)
            return JSONResponse(content={"message": "Invalid datatype"}, status_code=400)
    except Exception as e:
        logger.exception("Exception occurred while fetching legal case: %s", str(e))
        return JSONResponse(
            content={"message": "Internal Server Error"}, status_code=500
        )


@router.post("/archive-chat", tags=["ChatController"])
def archive_chat(
    request: ArchiveChatRequest,
    token=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    user_id = get_userid_by_token(token)
    session_id = request.session_id
    logger.debug("Archiving chat for session_id: %s, user_id: %s", session_id, user_id)
    archive_status = archive_session(
        user_id=user_id, session_id=session_id, db_session=session
    )
    if archive_status:
        logger.info("Chat archived for session_id: %s", session_id)
    else:
        logger.warning("Failed to archive chat for session_id: %s", session_id)
    return JSONResponse(content={"Success": archive_status}, status_code=200)


@router.post("/archive-all-chat", tags=["ChatController"])
def archive_all_chat(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(token)
    logger.debug("Archiving all chats for user_id: %s", user_id)
    archive_status = archive_all_session(user_id=user_id, db_session=session)
    if archive_status:
        logger.info("All chats archived for user_id: %s", user_id)
    else:
        logger.warning("Failed to archive all chats for user_id: %s", user_id)
    return JSONResponse(content={"Success": archive_status}, status_code=200)


@router.post("/get-archived-chats", tags=["ChatController"])
def get_all_archived_chat(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
) -> List[ArchivedSessionSummary]:
    user_id = get_userid_by_token(token)
    logger.debug("Fetching all archived chats for user_id: %s", user_id)
    archived_sessions = get_archived_sessions_by_user_id(
        user_id=user_id, db_session=session
    )
    logger.info("Retrieved %d archived sessions for user_id: %s", len(archived_sessions), user_id)
    return archived_sessions


@router.post("/delete-archive-chat", tags=["ChatController"])
def delete_archived_chat(
    request: DeleteSharedSessionRequest,
    token=Depends(JWTBearer()),
    session: Session = Depends(get_session),
):
    user_id = get_userid_by_token(token)
    session_id = request.session_id
    logger.debug("Deleting archived chat for session_id: %s, user_id: %s", session_id, user_id)
    deleted_status = delete_archived_session_by_id(
        user_id=user_id, session_id=session_id, db_session=session
    )
    if deleted_status:
        logger.info("Archived chat deleted for session_id: %s", session_id)
    else:
        logger.warning("Failed to delete archived chat for session_id: %s", session_id)
    return JSONResponse(
        content={"Success": deleted_status, "messages": "Deleted archived session."},
        status_code=200,
    )


@router.post("/delete-all-archive-chats", tags=["ChatController"])
def delete_all_archived_chats(
    token=Depends(JWTBearer()), session: Session = Depends(get_session)
):
    user_id = get_userid_by_token(token)
    logger.debug("Deleting all archived chats for user_id: %s", user_id)
    deleted_status = delete_archived_sessions_by_user_id(
        user_id=user_id, db_session=session
    )
    if deleted_status:
        logger.info("All archived chats deleted for user_id: %s", user_id)
    else:
        logger.warning("Failed to delete all archived chats for user_id: %s", user_id)
    return JSONResponse(
        content={"Success": deleted_status, "messages": "Deleted all archived chats."},
        status_code=200,
    )
