import os
import uuid
from typing import Optional

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.subject import Subject
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.repositories.document import document_repository
from app.services.processing import processing_service


# Supported document formats for the MVP
ALLOWED_EXTENSIONS = {
    "pdf",
    "docx",
    "pptx",
    "ppt",
    "png",
    "jpg",
    "jpeg",
}


class DocumentService:
    """
    Handles document upload, validation, processing, and deletion.
    """

    async def upload_document(
        self,
        db: AsyncSession,
        file: UploadFile,
        subject_id: uuid.UUID,
        category: str,
        user_id: Optional[uuid.UUID],
    ) -> Document:
        """
        Upload lifecycle:

        1. Validate subject
        2. Validate category
        3. Validate file type
        4. Save file to disk
        5. Create document database record
        6. Process document
           -> Extract text
           -> Semantic chunking
           -> Metadata extraction
           -> Store chunks
           -> Generate embeddings
           -> Index vectors
        7. Return processed document
        """

        # ---------------------------------------------------------
        # 1. Verify subject exists
        # ---------------------------------------------------------
        subject = await db.get(Subject, subject_id)

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The referenced Course Subject ID does not exist.",
            )

        # ---------------------------------------------------------
        # 2. Validate document category
        # ---------------------------------------------------------
        if category not in {"notes", "pyq", "book", "lab"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid metadata category. "
                    "Select notes, pyq, book, or lab."
                ),
            )

        # ---------------------------------------------------------
        # 3. Validate file extension
        # ---------------------------------------------------------
        original_name = file.filename or "unnamed_file"

        file_ext = (
            original_name.rsplit(".", 1)[-1].lower()
            if "." in original_name
            else ""
        )

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported format '.{file_ext}'. "
                    "Allowed formats: PDF, DOCX, PPTX, PPT, JPG, PNG."
                ),
            )

        # ---------------------------------------------------------
        # 4. Generate secure filename and save file
        # ---------------------------------------------------------
        secure_filename = f"{uuid.uuid4()}.{file_ext}"

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        storage_path = os.path.join(
            settings.UPLOAD_DIR,
            secure_filename,
        )

        try:
            file_bytes = await file.read()

            with open(storage_path, "wb") as buffer:
                buffer.write(file_bytes)

        except Exception as err:
            # Remove partially written file if necessary
            if os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                except OSError:
                    pass

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Disk writer operation failed: {str(err)}",
            )

        # ---------------------------------------------------------
        # 5. Create document metadata record
        # ---------------------------------------------------------
        doc_in = DocumentCreate(
            subject_id=subject_id,
            name=original_name,
            storage_path=storage_path,
            file_type=file_ext,
            category=category,
            uploaded_by=user_id,
        )

        try:
            document = await document_repository.create(
                db,
                obj_in=doc_in,
            )

        except Exception as err:
            # Database insert failed, so clean up uploaded file
            if os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                except OSError:
                    pass

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create document record: {str(err)}",
            )

        # ---------------------------------------------------------
        # 6. Process uploaded document
        # ---------------------------------------------------------
        try:
            document = await processing_service.process_document(
                db=db,
                document_id=document.id,
            )

        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {str(err)}",
            )

        # ---------------------------------------------------------
        # 7. Return processed document
        # ---------------------------------------------------------
        return document

    async def delete_document(
        self,
        db: AsyncSession,
        doc_id: uuid.UUID,
    ) -> Optional[Document]:
        """
        Deletes a document from:

        1. Vector database
        2. Physical file storage
        3. SQL database
        """

        # Find document
        doc = await document_repository.get_by_id(
            db,
            doc_id=doc_id,
        )

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        # ---------------------------------------------------------
        # 1. Delete vectors
        # ---------------------------------------------------------
        try:
            from app.services.vector_db import vector_db_service

            vector_db_service.delete_document_chunks(doc_id)

        except Exception as err:
            # Do not prevent document deletion if vector cleanup fails
            print(f"Error removing document vectors: {err}")

        # ---------------------------------------------------------
        # 2. Delete physical file
        # ---------------------------------------------------------
        if os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)

            except Exception as err:
                print(f"Error removing file from disk: {err}")

        # ---------------------------------------------------------
        # 3. Delete database record
        # ---------------------------------------------------------
        return await document_repository.delete(
            db,
            doc_id=doc_id,
        )


# Singleton service instance
document_service = DocumentService()