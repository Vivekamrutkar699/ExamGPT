import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate


class DocumentRepository:
    """
    Handles database operations for the Document ORM model.
    """

    async def get_by_id(self, db: AsyncSession, doc_id: uuid.UUID) -> Optional[Document]:
        """Fetch a document by its primary key ID."""
        result = await db.execute(select(Document).where(Document.id == doc_id))
        return result.scalars().first()

    async def get_by_subject(
        self, 
        db: AsyncSession, 
        subject_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Document]:
        """List all documents for a specific subject ID."""
        result = await db.execute(
            select(Document)
            .where(Document.subject_id == subject_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        subject_id: Optional[uuid.UUID] = None,
        category: Optional[str] = None
    ) -> List[Document]:
        """Query multi documents with subject and category filters."""
        query = select(Document)
        if subject_id:
            query = query.where(Document.subject_id == subject_id)
        if category:
            query = query.where(Document.category == category)
            
        result = await db.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: DocumentCreate) -> Document:
        """Register a new document metadata row."""
        db_obj = Document(
            subject_id=obj_in.subject_id,
            name=obj_in.name,
            storage_path=obj_in.storage_path,
            file_type=obj_in.file_type,
            category=obj_in.category,
            uploaded_by=obj_in.uploaded_by,
            processing_status="pending"
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, 
        db: AsyncSession, 
        db_obj: Document, 
        obj_in: DocumentUpdate
    ) -> Document:
        """Update fields like processing status or name details."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, doc_id: uuid.UUID) -> Optional[Document]:
        """Delete document from database."""
        db_obj = await self.get_by_id(db, doc_id=doc_id)
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
        return db_obj


# Singleton repository instance
document_repository = DocumentRepository()
