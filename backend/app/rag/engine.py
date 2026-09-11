import uuid
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.core.config import settings
from app.rag.query_processor import query_processor
from app.rag.hybrid_search import hybrid_searcher
from app.rag.reranker import reranker

# Setup AsyncOpenAI client
# Supports custom base URLs (like Ollama, LiteLLM, vLLM, or LocalAI)
openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY or "mock_key_offline",
    base_url=settings.OPENAI_API_BASE
)


class RAGEngine:
    """
    Coordinates the full Retrieval-Augmented Generation (RAG) pipeline:
    rewrites query, performs hybrid search, reranks results, packages contexts,
    calls LLM, and formats grounded citations.
    """

    def _format_context(self, chunks: List[Dict]) -> str:
        """Combine chunks into a structured context block for the LLM prompt."""
        context_blocks = []
        for idx, item in enumerate(chunks):
            doc_name = item["metadata"].get("page")
            page_str = f"Page {doc_name}" if doc_name else "Page Unknown"
            context_blocks.append(
                f"Source [{idx + 1}]: {item['category']} file (Chunk ID: {item['chunk_id']}, {page_str})\n"
                f"Content: {item['content']}\n"
            )
        return "\n---\n".join(context_blocks)

    def _generate_mock_response(self, query: str, chunks: List[Dict]) -> str:
        """Fallback mock answer when running offline with no OpenAI keys."""
        if not chunks:
            return (
                "Confidence: Low. Insufficient evidence in uploaded documents to answer.\n\n"
                "*(Note: Running in offline mock mode. No relevant study documents matched the query.)*"
            )

        citations_list = []
        for item in chunks:
            page = item["metadata"].get("page", 1)
            citations_list.append(f"[{item['category']}_docs, Page {page}]")

        best_chunk = chunks[0]["content"]
        citations_str = " ".join(citations_list)

        return (
            f"**[Mock Grounded Answer - OpenAI Key Not Set]**\n\n"
            f"Regarding your query on *'{query}'*, the retrieved notes state:\n"
            f"\"{best_chunk}\" {citations_str}\n\n"
            f"Confidence: High"
        )

    async def get_grounded_answer(
        self,
        db: AsyncSession,
        query: str,
        subject_id: uuid.UUID,
        category: Optional[str] = None,
        unit_tag: Optional[str] = None,
        limit: int = 4
    ) -> Tuple[str, List[Dict]]:
        """
        Executes the full RAG cycle, returns the grounded response string
        along with the list of supporting context chunks.
        """
        # 1. Intent Detection & Query Rewriting
        intent = query_processor.detect_intent(query)
        expanded_query = query_processor.rewrite_query(query)

        # 2. Hybrid Search (Dense Vector + Sparse Database overlap)
        raw_matches = await hybrid_searcher.search(
            db=db,
            query=expanded_query,
            subject_id=subject_id,
            limit=10,
            category=category,
            unit_tag=unit_tag
        )

        # 3. Rerank top results
        reranked_chunks = reranker.rerank(expanded_query, raw_matches)[:limit]

        # 4. In case no context is found, fail early to prevent hallucinations
        if not reranked_chunks:
            return "Confidence: Low. Insufficient evidence in uploaded documents to answer.", []

        # 5. Check if we need to fall back to Mock In-Process generator
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key_here":
            return self._generate_mock_response(query, reranked_chunks), reranked_chunks

        # 6. Build RAG Prompt context
        formatted_context = self._format_context(reranked_chunks)
        
        system_prompt = (
            "You are an expert Savitribai Phule Pune University (SPPU) Exam Intelligence Assistant.\n"
            "Your task is to answer the student's question based ONLY on the provided engineering context chunks.\n"
            "Do NOT use external training knowledge.\n\n"
            "Rules:\n"
            "1. Base your answer strictly on the provided context. If the context does not contain sufficient details to answer, state: 'Confidence: Low. Insufficient evidence in uploaded documents to answer.'\n"
            "2. For every assertion/fact you write, append a citation suffix pointing to the document and page index in brackets, e.g. [Syllabus_Doc.pdf, Page X].\n"
            "3. Format the answer clearly using Markdown with bold highlights, clean headers, or tables.\n"
            "4. Structure the response like a typical SPPU exam answer matching standard marking models (2 Marks = concise definition, 5 Marks = structured explanation, 10 Marks = detailed system elements).\n"
            "5. At the very end of your response, write a single line: 'Confidence: [High|Medium|Low]' based on how well the retrieved context covers the user's question.\n\n"
            f"Retrieved Context Chunks:\n{formatted_context}"
        )

        # 7. Execute ChatCompletion call
        try:
            response = await openai_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": expanded_query}
                ],
                temperature=0.2,  # low temperature to encourage strict factual recall
                max_tokens=800
            )
            return response.choices[0].message.content, reranked_chunks
        except Exception as e:
            # Fallback to local mockup if external API calls fail
            print(f"LLM API completion failed: {e}")
            return self._generate_mock_response(query, reranked_chunks) + f"\n\n*(Completion fallback due to error: {e})*", reranked_chunks


# Singleton instance
rag_engine = RAGEngine()
