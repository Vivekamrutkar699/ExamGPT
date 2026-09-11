import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import Chunk
from app.document_processing.parser import document_parser
from app.document_processing.chunking import SemanticChunker
from app.document_processing.metadata import metadata_extractor

chunker = SemanticChunker()


class ProcessingService:
    """
    Orchestrates the document processing lifecycle: updates status states,
    parses raw file contents, splits pages semantically, extracts syllabus metadata,
    and inserts chunks into the database.
    """

    async def process_document(
        self, 
        db: AsyncSession, 
        document_id: uuid.UUID
    ) -> Document:
        """
        Retrieves document, sets state to 'processing', runs parser, 
        groups text semantically, tags unit metadata, and commits chunks.
        """
        doc = await db.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document ID {document_id} not found in database.")

        # Set status to processing
        doc.processing_status = "processing"
        await db.commit()

        try:
            # 1. Parse text from storage path based on file extension
            pages = document_parser.extract_text(doc.storage_path, doc.file_type)
            
            chunk_count = 0
            last_unit_tag = None
            
            # 2. Iterate pages and run semantic chunker
            for page_data in pages:
                page_num = page_data["page"]
                page_text = page_data["text"]
                tables = page_data.get("tables", [])
                
                # Split page contents semantically
                page_chunks = chunker.create_chunks(page_text)
                
                for chunk_text in page_chunks:
                    # 3. Extract syllabus tagging (Units & Chapters)
                    meta = metadata_extractor.extract_metadata(chunk_text)
                    unit_tag = meta["unit_tag"]
                    section_title = meta["section_title"]
                    
                    # Heuristic fallback: if a chunk lacks a unit tag, inherit 
                    # from the previous chunk to preserve course alignment.
                    if not unit_tag and last_unit_tag:
                        unit_tag = last_unit_tag
                    elif unit_tag:
                        last_unit_tag = unit_tag
                        
                    # 4. Construct SQL Chunk ORM
                    db_chunk = Chunk(
                        document_id=doc.id,
                        chunk_index=chunk_count,
                        content=chunk_text,
                        section_title=section_title,
                        unit_tag=unit_tag,
                        metadata_json={
                            "page": page_num,
                            "tables": tables
                        }
                    )
                    db.add(db_chunk)
                    chunk_count += 1
            
            # Commit chunks first to register them in DB before querying for embeddings
            await db.commit()
            
            # 5. Index chunks in Vector Database
            from app.services.vector_db import vector_db_service
            await vector_db_service.index_document_chunks(db, doc.id)
            
            # 6. Complete state and commit final status
            doc.processing_status = "completed"
            await db.commit()
            await db.refresh(doc)
            return doc
            
        except Exception as err:
            # Rollback chunk transactions on exception and tag document as failed
            await db.rollback()
            doc.processing_status = "failed"
            await db.commit()
            await db.refresh(doc)
            raise err


# Singleton service instance
processing_service = ProcessingService()
