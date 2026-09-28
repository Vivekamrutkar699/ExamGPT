import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.chat import (
    ChatSessionCreate, 
    ChatSessionOut, 
    ChatMessageCreate, 
    ChatMessageOut,
    ChatQueryRequest,
    ChatHistoryItem,
    ChatQueryResponse,
)
from app.services.chat import chat_service
from app.repositories.chat import chat_repository
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_in: ChatSessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Open a new chat thread for a given subject vault.
    Supports both POST /api/v1/chats/ and POST /api/v1/chats/sessions.
    """
    return await chat_service.create_chat_session(
        db=db,
        user_id=current_user.id,
        subject_id=session_in.subject_id,
        title=session_in.title
    )


@router.get("/", response_model=List[ChatSessionOut])
async def list_my_chat_sessions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List all chat sessions created by the active student/faculty user context.
    """
    return await chat_repository.list_sessions_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )


@router.get("/sessions/subject/{subject_id}", response_model=List[ChatSessionOut])
async def list_chat_sessions_by_subject(
    subject_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    List all chat sessions created by the authenticated user for a specific course subject.
    Enforces user isolation and validates course subject existence.
    """
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The referenced Course Subject ID does not exist.",
        )

    return await chat_repository.list_sessions_by_user_and_subject(
        db=db,
        user_id=current_user.id,
        subject_id=subject_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{session_id}/messages", response_model=List[ChatMessageOut])
async def get_chat_message_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve chronological messages history (user/assistant) for a session thread.
    """
    session = await chat_repository.get_session_by_id(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found."
        )
        
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this chat session."
        )
        
    return await chat_repository.get_messages_by_session(db, session_id=session_id)


@router.post("/{session_id}/message", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    session_id: uuid.UUID,
    message_in: ChatMessageCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Send a message into the chat thread. Triggers LangGraph multi-agent 
    grounding checks and returns the assistant's reply with citations.
    """
    return await chat_service.send_message(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        content=message_in.content
    )


@router.get("/sessions/{session_id}/history", response_model=List[ChatHistoryItem])
@router.get("/{session_id}/history", response_model=List[ChatHistoryItem])
async def get_session_chat_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Retrieve conversational turn history (query, response, citations) for a session thread.
    Supports both GET /chats/sessions/{session_id}/history and GET /chats/{session_id}/history.
    """
    session = await chat_repository.get_session_by_id(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this chat session.",
        )

    messages = await chat_repository.get_messages_by_session(db, session_id=session_id)
    history: List[ChatHistoryItem] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.role == "user":
            if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                ast = messages[i + 1]
                history.append(
                    ChatHistoryItem(
                        id=ast.id,
                        query=msg.content,
                        response=ast.content,
                        citations=ast.citations_json or [],
                        created_at=ast.created_at,
                    )
                )
                i += 2
            else:
                history.append(
                    ChatHistoryItem(
                        id=msg.id,
                        query=msg.content,
                        response="",
                        citations=[],
                        created_at=msg.created_at,
                    )
                )
                i += 1
        elif msg.role == "assistant":
            history.append(
                ChatHistoryItem(
                    id=msg.id,
                    query="",
                    response=msg.content,
                    citations=msg.citations_json or [],
                    created_at=msg.created_at,
                )
            )
            i += 1
        else:
            i += 1

    return history


@router.post("/sessions/{session_id}/query", response_model=ChatQueryResponse)
@router.post("/{session_id}/query", response_model=ChatQueryResponse)
async def query_chat_session(
    session_id: uuid.UUID,
    query_in: ChatQueryRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Submit a user question to the AI Copilot for a chat session.
    Triggers LangGraph multi-agent grounding checks, retrieves citations,
    and returns assistant response.
    Supports both POST /chats/sessions/{session_id}/query and POST /chats/{session_id}/query.
    """
    session = await chat_repository.get_session_by_id(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this chat session.",
        )

    query_text = (query_in.query or query_in.content or "").strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query content cannot be empty.",
        )

    reply_message = await chat_service.send_message(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        content=query_text,
    )

    return ChatQueryResponse(
        id=reply_message.id,
        session_id=reply_message.session_id,
        role=reply_message.role,
        content=reply_message.content,
        response=reply_message.content,
        query=query_text,
        citations=reply_message.citations_json or [],
        citations_json=reply_message.citations_json or [],
        created_at=reply_message.created_at,
    )
