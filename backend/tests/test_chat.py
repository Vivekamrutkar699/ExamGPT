import asyncio
import uuid
from unittest.mock import patch

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.services.processing import processing_service
from app.services.chat import chat_service
from app.repositories.chat import chat_repository


async def test_chat_assistant_flow():
    print("Beginning Chat Assistant E2E Service Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"chatter_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Chatter Tester",
            role="student"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-CHAT-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Chat Flow Integration",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        # 2. Add Document
        test_doc = Document(
            subject_id=test_subject.id,
            name="chat_notes.pdf",
            storage_path="mock_uploads/chat_notes.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        # 3. Mock Parser Output containing target keywords
        mock_extracted_pages = [
            {
                "page": 1,
                "text": "UNIT 1: SYSTEM SOFTWARE DESIGN.\nDynamic linking loads library binaries at runtime, saving memory overhead.\nStatic linking bundles library binaries at compile time.",
                "tables": []
            }
        ]

        # 4. Patch parser and process (triggers Chunk creation + auto indexing)
        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        print("Document indexed. Creating conversational session...")

        # 5. Create new chat session
        session = await chat_service.create_chat_session(
            db=db,
            user_id=test_user.id,
            subject_id=test_subject.id,
            title="Syllabus Linkers Prep Session"
        )
        assert session.title == "Syllabus Linkers Prep Session"
        assert session.subject_id == test_subject.id
        print("OK: Chat session initialized successfully.")

        # 6. Send user message (should route to rag_fallback node)
        print("Sending user message: 'what are the benefits of dynamic linking?'...")
        reply = await chat_service.send_message(
            db=db,
            session_id=session.id,
            user_id=test_user.id,
            content="what are the benefits of dynamic linking?"
        )
        
        assert reply.role == "assistant"
        assert "dynamic linking" in reply.content.lower() or "mock" in reply.content.lower()
        assert len(reply.citations_json) > 0
        print(f"OK: Received assistant response: {reply.content[:100]}...")
        print(f"OK: Citations mapped: {reply.citations_json}")

        # 7. Verify database message history
        history = await chat_repository.get_messages_by_session(db, session_id=session.id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        print("OK: Chronological message history in database verified.")
        
        # 8. Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Chat Assistant E2E Service Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_chat_assistant_flow())
