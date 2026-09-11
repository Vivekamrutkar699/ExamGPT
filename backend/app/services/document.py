import os
import uuid
from typing import Optional, List
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.subject import Subject
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.repositories.document import document_repository

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "ppt", "png", "jpg", "jpeg", "zip"}


class DocumentService:
    """
    Implements business operations for file uploading, validation, and physical resource deletion.
    """
    
    async def upload_document(
        self,
        db: AsyncSession,
        file: UploadFile,
        subject_id: uuid.UUID,
        category: str,
        user_id: Optional[uuid.UUID]
    ) -> Document:
        """
        Validates course Subject existence, file formats, registers row parameters,
        and saves the raw binary contents securely to the configured upload folder.
        """
        # 1. Verify subject validity
        subject = await db.get(Subject, subject_id)
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The referenced Course Subject ID does not exist."
            )
            
        # 2. Check metadata parameters
        if category not in {"notes", "pyq", "book", "lab"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid metadata category. Select notes, pyq, book, or lab."
            )

        # 3. Check filename extension
        original_name = file.filename or "unnamed_file"
        file_ext = original_name.split(".")[-1].lower() if "." in original_name else ""
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format '.{file_ext}'. Allowed formats: PDF, DOCX, PPTX, JPG, PNG, ZIP."
            )

        # 4. Generate random secure filename to prevent collision and path traversal
        secure_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # Ensure configuration upload path exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        storage_path = os.path.join(settings.UPLOAD_DIR, secure_filename)

        # 5. Write bytes asynchronously to local disk
        try:
            file_bytes = await file.read()
            with open(storage_path, "wb") as buffer:
                buffer.write(file_bytes)
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Disk writer operation failed: {str(err)}"
            )

        # 6. Insert metadata index mapping
        doc_in = DocumentCreate(
            subject_id=subject_id,
            name=original_name,
            storage_path=storage_path,
            file_type=file_ext,
            category=category,
            uploaded_by=user_id
        )
        return await document_repository.create(db, obj_in=doc_in)

    async def delete_document(
        self, 
        db: AsyncSession, 
        doc_id: uuid.UUID
    ) -> Optional[Document]:
        """
        Removes metadata mappings from SQL database and deletes physical files from storage.
        """
        doc = await document_repository.get_by_id(db, doc_id=doc_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found."
            )
            
        # Delete file from local filesystem
        if os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except Exception as err:
                # Log filesystem removal error but continue to clean DB entries
                print(f"Error removing file from disk: {err}")
                
        # Purge vectors from Vector Database
        from app.services.vector_db import vector_db_service
        vector_db_service.delete_document_chunks(doc_id)
                
        return await document_repository.delete(db, doc_id=doc_id)


# Singleton service instance
document_service = DocumentService()
