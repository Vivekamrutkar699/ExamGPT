import asyncio
import uuid
from unittest.mock import patch
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.processing import processing_service
from app.services.document import document_service
from app.rag.vector_store import vector_store_manager


async def test_vector_indexing_and_search():
    print("Beginning Vector Database Integration and Semantic Search Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"vectorist_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Vector Search Test Admin",
            role="admin"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-VEC-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Vector Database Indexing",
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
            name="vector_architecture_syllabus.pdf",
            storage_path="mock_uploads/vector_arch.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        # 3. Mock Parser Output containing Unit tags
        mock_extracted_pages = [
            {
                "page": 1,
                "text": "UNIT 1: VECTOR PROCESSORS.\nVector processing exploits pipeline structures.\nVector registers store multiple data points simultaneously.",
                "tables": []
            },
            {
                "page": 2,
                "text": "UNIT II: ARRAY PROCESSORS.\nArray processors execute instruction loops on spatial grids.\nThis is parallel computing architecture.",
                "tables": []
            }
        ]

        # 4. Patch parser and process (triggers Chunk creation + auto indexing)
        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        print("Document processed and chunks successfully indexed in Vector DB.")

        # 5. Search Check 1: Match query under Subject
        results_sub = vector_store_manager.search(
            query="pipeline structures in vector processors",
            subject_id=test_subject.id,
            limit=2
        )
        assert len(results_sub) > 0
        assert "VECTOR PROCESSORS" in results_sub[0]["content"]
        assert results_sub[0]["unit_tag"] == "Unit 1"
        assert results_sub[0]["score"] > 0.4
        print(f"Search match 1 passed. Best score: {results_sub[0]['score']}")

        # 6. Search Check 2: Metadata filtering isolation (different Subject)
        different_subject_id = uuid.uuid4()
        results_diff = vector_store_manager.search(
            query="pipeline structures in vector processors",
            subject_id=different_subject_id,
            limit=2
        )
        # Should return 0 results because of subject filter enforcement
        assert len(results_diff) == 0
        print("Search match 2 (Subject isolation filter) passed successfully.")

        # 7. Search Check 3: Unit Tag metadata filter
        results_unit = vector_store_manager.search(
            query="parallel computing elements",
            subject_id=test_subject.id,
            limit=2,
            unit_tag="Unit 2"
        )
        assert len(results_unit) > 0
        assert results_unit[0]["unit_tag"] == "Unit 2"
        assert "ARRAY PROCESSORS" in results_unit[0]["content"]
        print("Search match 3 (Unit tag metadata isolation) passed successfully.")

        # 8. Delete document (triggers vector indexes cleanup cascade)
        await document_service.delete_document(db, test_doc.id)
        
        # Verify vectors are gone
        results_after_delete = vector_store_manager.search(
            query="pipeline structures in vector processors",
            subject_id=test_subject.id,
            limit=2
        )
        assert len(results_after_delete) == 0
        print("Vector deletion cleanup cascade verified.")
        
        # Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Vector Database Integration and Semantic Search Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_vector_indexing_and_search())
