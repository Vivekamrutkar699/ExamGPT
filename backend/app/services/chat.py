import uuid
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.repositories.chat import chat_repository
from app.services.agents import agent_orchestration_service


class ChatService:
    """
    Coordinates chat message persistence and routes dialog flows
    through the compiled LangGraph agents workflow.
    """

    async def create_chat_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        title: str
    ) -> ChatSession:
        """Initialize a new conversation thread."""
        from app.models.subject import Subject
        # Verify subject exists first
        subject = await db.get(Subject, subject_id)
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course Subject ID not found."
            )
            
        from app.schemas.chat import ChatSessionCreate
        obj_in = ChatSessionCreate(subject_id=subject_id, title=title)
        return await chat_repository.create_session(db, user_id=user_id, obj_in=obj_in)

    async def send_message(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str
    ) -> ChatMessage:
        """
        Processes an incoming user message, triggers the LangGraph agent state graph,
        logs chat entries in database tables, and indexes citation references.
        """
        # 1. Fetch active session metadata
        session = await chat_repository.get_session_by_id(db, session_id=session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found."
            )
            
        # Ensure session owner matches current user context
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this chat session."
            )

        # 2. Append User query message to database records
        await chat_repository.add_message(
            db=db,
            session_id=session_id,
            role="user",
            content=content
        )

        # 3. Invoke LangGraph Orchestration State workflow
        # The graph executes intent detection, RAG retrieval, predictions, or evaluations
        graph_state = await agent_orchestration_service.run_agent_workflow(
            query=content,
            subject_id=session.subject_id,
            user_id=user_id
        )

        # 4. Map returned context chunks to citation records schema
        raw_chunks = graph_state.get("context_chunks", [])
        citations = []
        for c in raw_chunks:
            page = c.get("metadata", {}).get("page", 1)
            citations.append({
                "chunk_id": str(c.get("chunk_id")),
                "content": c.get("content", "")[:120],
                "page": page,
                "category": c.get("category", "notes")
            })

        # 5. Save and return Assistant reply
        assistant_reply = graph_state.get("response", "I encountered an error formulating a response.")
        
        reply_message = await chat_repository.add_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=assistant_reply,
            citations=citations
        )
        
        return reply_message


# Singleton service instance
chat_service = ChatService()
