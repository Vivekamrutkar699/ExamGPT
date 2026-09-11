import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import Chunk
from app.rag.vector_store import vector_store_manager


class VectorDBService:
    """
    Coordinates SQL database chunk queries and maps them to vector store updates.
    """

    async def index_document_chunks(
        self, 
        db: AsyncSession, 
        document_id: uuid.UUID
    ) -> None:
        """
        Loads committed chunks from DB and passes them to VectorStoreManager for embedding.
        """
        doc = await db.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document ID {document_id} not found in database.")

        # Query all chunks belonging to this document
        result = await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return

        # Map chunks to indexing data contracts
        chunks_data = [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "subject_id": doc.subject_id,
                "content": c.content,
                "unit_tag": c.unit_tag,
                "category": doc.category,
                "metadata": c.metadata_json
            }
            for c in chunks
        ]

        # Bulk write to vector database
        vector_store_manager.add_chunks(chunks_data)

    def delete_document_chunks(self, document_id: uuid.UUID) -> None:
        """
        Purges vector database index entries matching this document.
        """
        vector_store_manager.delete_document_vectors(document_id)


# Singleton service instance
vector_db_service = VectorDBService()
