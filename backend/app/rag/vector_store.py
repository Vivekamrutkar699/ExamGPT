import os
import json
import uuid
import numpy as np
from typing import List, Optional, Dict

from app.core.config import settings
from app.document_processing.chunking import get_embedding_model


class VectorStoreManager:
    """
    Abstractions wrapper managing dynamic vector index storage.
    Uses local files (json/numpy) to query embeddings, compute similarities,
    and enforce strict metadata scopes.
    """
    
    def __init__(self):
        self.index_path = os.path.join(settings.VECTOR_DB_DIR, "index.json")
        self._ensure_storage()

    def _ensure_storage(self):
        """Creates vector directory and empty index file if missing."""
        os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
        if not os.path.exists(self.index_path):
            with open(self.index_path, "w") as f:
                json.dump([], f)

    def _load_index(self) -> List[Dict]:
        """Load all index entities from disk."""
        self._ensure_storage()
        try:
            with open(self.index_path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_index(self, data: List[Dict]):
        """Save list of index entities to disk."""
        self._ensure_storage()
        with open(self.index_path, "w") as f:
            json.dump(data, f)

    def add_chunks(self, chunks_data: List[Dict]) -> None:
        """
        Takes raw chunks metadata, encodes contents using SentenceTransformer,
        and saves records to the index collection.
        """
        if not chunks_data:
            return

        # 1. Load active index list
        index = self._load_index()

        # 2. Extract contents and build embeddings in batch
        contents = [c["content"] for c in chunks_data]
        model = get_embedding_model()
        embeddings = model.encode(contents)

        # 3. Create items
        for item, emb in zip(chunks_data, embeddings):
            index.append({
                "chunk_id": str(item["chunk_id"]),
                "document_id": str(item["document_id"]),
                "subject_id": str(item["subject_id"]),
                "content": item["content"],
                "unit_tag": item.get("unit_tag"),
                "category": item.get("category"),
                "metadata": item.get("metadata", {}),
                "embedding": emb.tolist()  # serialize vector to floats
            })

        # 4. Save back to disk
        self._save_index(index)

    def delete_document_vectors(self, document_id: uuid.UUID) -> None:
        """Purge all index entries matching the target Document ID."""
        doc_id_str = str(document_id)
        index = self._load_index()
        
        # Filter out items that match the document_id
        filtered_index = [item for item in index if item["document_id"] != doc_id_str]
        
        self._save_index(filtered_index)

    def search(
        self,
        query: str,
        subject_id: uuid.UUID,
        limit: int = 5,
        category: Optional[str] = None,
        unit_tag: Optional[str] = None
    ) -> List[Dict]:
        """
        Encodes query string, applies strict metadata constraints (subject, category, unit),
        calculates cosine similarity distances, and returns top results.
        """
        sub_id_str = str(subject_id)
        index = self._load_index()

        # 1. Apply metadata filters to prevent context leakage
        filtered_items = [
            item for item in index 
            if item["subject_id"] == sub_id_str
        ]
        
        if category:
            filtered_items = [item for item in filtered_items if item["category"] == category]
            
        if unit_tag:
            filtered_items = [item for item in filtered_items if item["unit_tag"] == unit_tag]

        if not filtered_items:
            return []

        # 2. Encode search query
        model = get_embedding_model()
        query_emb = model.encode(query)

        # 3. Calculate cosine similarities
        results = []
        for item in filtered_items:
            item_emb = np.array(item["embedding"])
            # Cosine similarity
            dot_product = np.dot(query_emb, item_emb)
            norm_q = np.linalg.norm(query_emb)
            norm_i = np.linalg.norm(item_emb)
            
            similarity = float(dot_product / (norm_q * norm_i)) if norm_q > 0 and norm_i > 0 else 0.0
            
            results.append({
                "chunk_id": item["chunk_id"],
                "content": item["content"],
                "unit_tag": item["unit_tag"],
                "category": item["category"],
                "metadata": item["metadata"],
                "score": similarity
            })

        # 4. Sort and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


# Singleton instance
vector_store_manager = VectorStoreManager()
