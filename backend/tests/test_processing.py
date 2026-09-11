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


async def test_processing_orchestration():
    print("Beginning Document Processing Service Integration Test...")
    
    # 1. Setup temporary course Subject, User, and Document
    async with SessionLocal() as db:
        test_user = User(
            email=f"processor_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Processing Tester",
            role="admin"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-PROCESS-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Document Processing Flow",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        test_doc = Document(
            subject_id=test_subject.id,
            name="system_software_syllabus.pdf",
            storage_path="mock_uploads/system_software.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)
        
        # 2. Mock DocumentParser extraction output to isolate logic test
        mock_extracted_pages = [
            {
                "page": 1,
                "text": "UNIT 1: INTRODUCTION TO SYSTEM SOFTWARE.\nSystem software acts as an interface layer.\nWe discuss loaders, linkers, and assemblers here.",
                "tables": []
            },
            {
                "page": 2,
                "text": "UNIT II: COMPILERS AND INTERPRETERS.\nCompilers translate high-level program codes to machine targets.\nThis is section 2.1 compiler architectures.",
                "tables": []
            }
        ]
        
        # 3. Patch extract_text and run processor
        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            processed_doc = await processing_service.process_document(db, test_doc.id)
            
        # 4. Assertions on Document state
        assert processed_doc.processing_status == "completed"
        
        # 5. Assertions on Chunks saved
        result = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == test_doc.id)
            .order_by(Chunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        
        assert len(chunks) >= 2
        
        # Verify Unit tags are extracted and mapped
        assert chunks[0].unit_tag == "Unit 1"
        assert chunks[1].unit_tag == "Unit 2"
        
        print(f"Validated {len(chunks)} chunks in DB:")
        for c in chunks:
            print(f"  Chunk {c.chunk_index}: Unit={c.unit_tag}, Title={c.section_title}, Content={c.content[:40]}...")
            
        # 6. Cleanup
        await db.delete(test_doc)  # cascade deletes chunks
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        
        # Verify cascades
        chunks_check = await db.execute(select(Chunk).where(Chunk.document_id == test_doc.id))
        assert len(chunks_check.scalars().all()) == 0
        
        print("Cascaded SQL purge verified.")
        print("Document Processing Service Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_processing_orchestration())
