import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.chat import (
    ChatSessionCreate, 
    ChatSessionOut, 
    ChatMessageCreate, 
    ChatMessageOut
)
from app.services.chat import chat_service
from app.repositories.chat import chat_repository
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_in: ChatSessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Open a new chat thread for a given subject vault.
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
