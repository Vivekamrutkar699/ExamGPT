import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import ChatSessionCreate


class ChatRepository:
    """
    Manages database CRUD transactions for ChatSessions and ChatMessages.
    """

    async def create_session(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        obj_in: ChatSessionCreate
    ) -> ChatSession:
        """Create a new conversational session linked to a subject."""
        db_session = ChatSession(
            user_id=user_id,
            subject_id=obj_in.subject_id,
            title=obj_in.title
        )
        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)
        return db_session

    async def get_session_by_id(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> Optional[ChatSession]:
        """Fetch details of a single chat session."""
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        return result.scalars().first()

    async def list_sessions_by_user(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ChatSession]:
        """List paginated chat sessions created by a user."""
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_message(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        role: str,
        content: str,
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> ChatMessage:
        """Append a user or assistant message to the session history."""
        db_message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations_json=citations
        )
        db.add(db_message)
        await db.commit()
        await db.refresh(db_message)
        return db_message

    async def get_messages_by_session(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> List[ChatMessage]:
        """Fetch all messages for a session, sorted chronologically."""
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())


# Singleton repository instance
chat_repository = ChatRepository()
