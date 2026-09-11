import asyncio
import os
import io
import uuid
from fastapi import UploadFile
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.services.document import document_service


async def test_document_upload_flow():
    print("Beginning Document Ingestion Service Integration Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"uploader_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="dummy_password",
            full_name="Upload Tester",
            role="faculty"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-TEST-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Subject Ingestion",
            semester=5,
            branch="Information Technology"
        )
        db.add(test_subject)
        
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        # 2. Mock a multipart binary file upload (PDF format)
        dummy_file_content = b"%PDF-1.4 Mock PDF syllabus contents for SPPU AI testing."
        mock_file = UploadFile(
            file=io.BytesIO(dummy_file_content),
            filename="syllabus_ai_test_2026.pdf"
        )
        
        # 3. Call service to upload
        doc_record = await document_service.upload_document(
            db=db,
            file=mock_file,
            subject_id=test_subject.id,
            category="notes",
            user_id=test_user.id
        )
        
        # 4. Assertions
        assert doc_record.name == "syllabus_ai_test_2026.pdf"
        assert doc_record.file_type == "pdf"
        assert doc_record.category == "notes"
        assert doc_record.processing_status == "pending"
        assert doc_record.uploaded_by == test_user.id
        assert doc_record.subject_id == test_subject.id
        
        # Verify file is written to local disk
        assert os.path.exists(doc_record.storage_path) is True
        print(f"File stored safely at: {doc_record.storage_path}")
        
        # 5. Clean up via service delete (should remove file and database entity)
        storage_path = doc_record.storage_path
        await document_service.delete_document(db=db, doc_id=doc_record.id)
        
        # Check files and entities are cleaned up
        assert os.path.exists(storage_path) is False
        db_check = await db.get(Document, doc_record.id)
        assert db_check is None
        
        # Remove subject & user
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Disk and DB cleanup validated successfully.")
        print("Document Ingestion Service Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_document_upload_flow())
