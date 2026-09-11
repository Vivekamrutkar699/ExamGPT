import re
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

_model_instance = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy load the sentence transformer model to save memory on server startup."""
    global _model_instance
    if _model_instance is None:
        # Load local bi-encoder from huggingface cache or download
        _model_instance = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model_instance


class SemanticChunker:
    """
    Groups document text pages into context-rich semantic segments
    using sentence embedding similarity checks instead of rigid character counts.
    """

    def split_sentences(self, text: str) -> list[str]:
        """
        Split raw text block into individual sentences using regex,
        avoiding dependencies on NLTK punkt datasets to ensure offline reliability.
        """
        # Split sentences by period, question mark, or exclamation, followed by space,
        # avoiding abbreviations like Prof., Dr., e.g., i.e.
        sentence_end = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
        sentences = sentence_end.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Compute the cosine similarity between two vectors."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def create_chunks(
        self, 
        text: str, 
        target_similarity: float = 0.6,
        max_words: int = 400,
        min_words: int = 50
    ) -> list[str]:
        """
        Split a document page/text into sentences, compare sentence embeddings,
        and group them semantically into chunks.
        """
        sentences = self.split_sentences(text)
        if not sentences:
            return []

        if len(sentences) == 1:
            return sentences

        # 1. Generate sentence embeddings
        model = get_embedding_model()
        embeddings = model.encode(sentences)

        chunks = []
        current_chunk_sentences = [sentences[0]]
        
        # 2. Iterate and compare adjacent sentences
        for idx in range(len(sentences) - 1):
            s1_emb = embeddings[idx]
            s2_emb = embeddings[idx + 1]
            next_sentence = sentences[idx + 1]
            
            similarity = self.cosine_similarity(s1_emb, s2_emb)
            
            # Count words in current chunk if we add the next sentence
            current_words_count = sum(len(s.split()) for s in current_chunk_sentences)
            next_words_count = len(next_sentence.split())
            
            # Boundary conditions:
            # - If similarity drops below threshold (semantic shift) AND we meet minimum size, split.
            # - If chunk exceeds max_words, force a split to preserve LLM token context size.
            if (similarity < target_similarity and current_words_count >= min_words) or \
               (current_words_count + next_words_count > max_words):
                
                chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [next_sentence]
            else:
                current_chunk_sentences.append(next_sentence)
                
        # Append residual sentences
        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences))

        return chunks
