import asyncio
import uuid
from datetime import datetime
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.question import Question


async def test_database_flow():
    print("Beginning Database Integration Test Flow...")
    
    # 1. Open Session
    async with SessionLocal() as db:
        print("Connected to DB successfully.")
        
        # Cleanup past test runs
        await db.execute(select(Subject)) # trigger simple read
        
        # 2. Insert User
        test_user = User(
            email=f"test_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_test_password",
            full_name="Test DB Administrator",
            role="admin"
        )
        db.add(test_user)
        
        # 3. Insert Subject
        test_subject = Subject(
            code=f"CS-{uuid.uuid4().hex[:4].upper()}",
            name="Advanced Artificial Intelligence",
            semester=7,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        
        # Commit to generate IDs
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        print(f"Created User: {test_user.email} (ID: {test_user.id})")
        print(f"Created Subject: {test_subject.code} (ID: {test_subject.id})")
        
        # 4. Insert Document linked to Subject & User
        test_doc = Document(
            subject_id=test_subject.id,
            name="AI_Unit_1_Notes.pdf",
            storage_path="/uploads/ai_unit_1.pdf",
            file_type="pdf",
            category="notes",
            processing_status="completed",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)
        print(f"Created Document: {test_doc.name} (ID: {test_doc.id})")
        
        # 5. Insert Chunk linked to Document
        test_chunk = Chunk(
            document_id=test_doc.id,
            chunk_index=0,
            content="This is the semantic content for Unit 1 of advanced artificial intelligence syllabus.",
            section_title="Introduction to AI Agents",
            unit_tag="Unit 1",
            metadata_json={"page": 1, "coordinates": [100, 200, 300, 400]}
        )
        db.add(test_chunk)
        
        # 6. Insert Question linked to Subject
        test_question = Question(
            subject_id=test_subject.id,
            text="Explain the structure of an AI agent and its relationship with the environment.",
            marks_weight=10,
            unit_tag="Unit 1",
            chapter="AI Agent Concepts",
            is_pyq=True,
            occurrences=3
        )
        db.add(test_question)
        await db.commit()
        await db.refresh(test_chunk)
        await db.refresh(test_question)
        print("Created Chunks and Questions.")
        
        # 7. Verification Queries (Join)
        result = await db.execute(
            select(Document, Subject)
            .join(Subject, Document.subject_id == Subject.id)
            .where(Document.id == test_doc.id)
        )
        doc_record, sub_record = result.one()
        assert doc_record.name == "AI_Unit_1_Notes.pdf"
        assert sub_record.code == test_subject.code
        print("Join query assertions passed successfully.")
        
        # Cleanup
        await db.delete(test_subject)  # Should cascade delete Document, Chunk, and Question
        await db.delete(test_user)
        await db.commit()
        print("Cleaned up database entries safely.")
        print("Database Integration Test Flow: PASSED")


if __name__ == "__main__":
    asyncio.run(test_database_flow())
