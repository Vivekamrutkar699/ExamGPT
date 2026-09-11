import asyncio
import uuid
from unittest.mock import patch
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.services.processing import processing_service
from app.services.document import document_service
from app.rag.engine import rag_engine


async def test_rag_grounding_flow():
    print("Beginning RAG Engine Integration Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"ragger_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="RAG Test Admin",
            role="admin"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-RAG-{uuid.uuid4().hex[:4].upper()}",
            name="Testing RAG Engine Integrations",
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
            name="system_programming_notes.pdf",
            storage_path="mock_uploads/sys_prog.pdf",
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
                "text": "UNIT 1: LOADERS AND LINKERS.\nLinkers combine multiple object files into a single executable binary.\nLoaders allocate memory and copy program segments to RAM.",
                "tables": []
            },
            {
                "page": 2,
                "text": "UNIT II: COMPILERS AND PARSERS.\nCompilers analyze grammar and generate code targets.\nParsers construct parse trees from lexical tokens.",
                "tables": []
            }
        ]

        # 4. Patch parser and process (triggers Chunk creation + auto indexing)
        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        print("Document processed. Running RAG grounded queries...")

        # 5. Call RAG engine with target query (should match Unit 1 keywords)
        query = "what is the function of linkers in system programming?"
        answer, contexts = await rag_engine.get_grounded_answer(
            db=db,
            query=query,
            subject_id=test_subject.id
        )
        
        # 6. Assertions
        assert len(contexts) > 0
        assert contexts[0]["unit_tag"] == "Unit 1"
        assert "LOADERS AND LINKERS" in contexts[0]["content"]
        
        # Check answer format includes citations and confidence ratings
        assert "Confidence:" in answer
        assert "notes" in answer or "completed" in answer or "Mock" in answer
        
        print("\nRAG Grounded Answer Output:")
        print("-" * 50)
        print(answer)
        print("-" * 50)
        print("Grounded RAG query assertions passed successfully.")
        
        # 7. Cleanup
        await document_service.delete_document(db, test_doc.id)
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("RAG Engine Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_rag_grounding_flow())
