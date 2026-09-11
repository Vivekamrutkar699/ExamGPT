import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.document import DocumentOut
from app.services.document import document_service
from app.repositories.document import document_repository
from app.models.user import User

router = APIRouter()


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    subject_id: uuid.UUID = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Ingest a new syllabus reference file (PDF, DOCX, PPTX, image or ZIP).
    Saves binary stream securely and catalogs indexing metadata properties.
    """
    return await document_service.upload_document(
        db=db,
        file=file,
        subject_id=subject_id,
        category=category,
        user_id=current_user.id
    )


@router.get("/", response_model=List[DocumentOut])
async def list_documents(
    subject_id: Optional[uuid.UUID] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve list of uploaded documents, filtered optionally by course branch ID and category tags.
    """
    return await document_repository.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        subject_id=subject_id,
        category=category
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document_details(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve detailed status parameters for a single document.
    """
    doc = await document_repository.get_by_id(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
    return doc


@router.delete("/{document_id}", response_model=DocumentOut)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Deletes mapping parameters from database records and removes file from file system.
    """
    # Expose validation that only admins/faculty or the owner can delete
    doc = await document_repository.get_by_id(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    if current_user.role not in {"admin", "faculty"} and doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this file."
        )
        
    return await document_service.delete_document(db, doc_id=document_id)
