import uuid
from typing import List, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.core.config import settings
from app.rag.query_processor import query_processor
from app.rag.hybrid_search import hybrid_searcher
from app.rag.reranker import reranker


# Ollama exposes an OpenAI-compatible API.
# The API key is only required by the OpenAI client interface;
# Ollama itself does not require a real OpenAI API key.
openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY or "ollama",
    base_url=settings.OPENAI_API_BASE or "http://localhost:11434/v1",
)


class RAGEngine:
    """
    Coordinates the complete Retrieval-Augmented Generation pipeline:

    1. Detect query intent
    2. Rewrite/expand the query
    3. Perform hybrid retrieval
    4. Rerank retrieved chunks
    5. Build a grounded prompt
    6. Generate an answer using the configured local LLM
    7. Return the answer together with supporting chunks
    """

    def _format_context(self, chunks: List[Dict]) -> str:
        """Combine retrieved chunks into structured LLM context."""

        context_blocks = []

        for idx, item in enumerate(chunks):
            metadata = item.get("metadata", {})

            page = metadata.get("page")
            document_name = (
                metadata.get("document_name")
                or metadata.get("filename")
                or f"{item.get('category', 'study')} document"
            )

            page_str = f"Page {page}" if page else "Page Unknown"

            context_blocks.append(
                f"Source [{idx + 1}]: {document_name}, {page_str}\n"
                f"Category: {item.get('category', 'unknown')}\n"
                f"Chunk ID: {item.get('chunk_id', 'unknown')}\n"
                f"Content:\n{item.get('content', '')}\n"
            )

        return "\n---\n".join(context_blocks)

    async def _generate_llm_response(
        self,
        query: str,
        expanded_query: str,
        context: str,
    ) -> str:
        """Generate a grounded answer using the configured LLM."""

        system_prompt = (
            "You are an expert Savitribai Phule Pune University (SPPU) "
            "Exam Intelligence Assistant.\n\n"

            "Your task is to answer the student's question using ONLY "
            "the retrieved engineering study material provided below.\n\n"

            "IMPORTANT RULES:\n"
            "1. Do not use external knowledge when it is not supported by "
            "the retrieved context.\n"
            "2. If the context does not contain enough information, clearly "
            "state: 'Confidence: Low. Insufficient evidence in uploaded "
            "documents to answer.'\n"
            "3. Do not invent facts, examples, formulas, definitions, or "
            "citations.\n"
            "4. Cite supporting sources using the source numbers provided "
            "in the context, for example [Source 1, Page 4].\n"
            "5. Write in clear Markdown suitable for an engineering student.\n"
            "6. Prefer structured exam-oriented answers with headings, "
            "bullet points, numbered steps, tables, or formulas when "
            "appropriate.\n"
            "7. For short questions, be concise. For descriptive questions, "
            "provide a sufficiently detailed explanation.\n"
            "8. At the end, provide exactly one confidence line:\n"
            "Confidence: High\n"
            "or\n"
            "Confidence: Medium\n"
            "or\n"
            "Confidence: Low\n\n"

            f"Retrieved study material:\n\n{context}"
        )

        response = await openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": expanded_query or query,
                },
            ],
            temperature=0.2,
            max_tokens=800,
        )

        answer = response.choices[0].message.content

        if not answer:
            raise RuntimeError("The local LLM returned an empty response.")

        return answer.strip()

    async def get_grounded_answer(
        self,
        db: AsyncSession,
        query: str,
        subject_id: uuid.UUID,
        category: Optional[str] = None,
        unit_tag: Optional[str] = None,
        limit: int = 4,
    ) -> Tuple[str, List[Dict]]:
        """
        Execute the complete RAG pipeline and return:

        (grounded_answer, supporting_chunks)
        """

        # ---------------------------------------------------------
        # 1. Query understanding
        # ---------------------------------------------------------

        intent = query_processor.detect_intent(query)
        expanded_query = query_processor.rewrite_query(query)

        # Keep intent available for future routing/analytics.
        # The current RAG path uses the expanded query for retrieval.
        _ = intent

        # ---------------------------------------------------------
        # 2. Hybrid retrieval
        # ---------------------------------------------------------

        raw_matches = await hybrid_searcher.search(
            db=db,
            query=expanded_query,
            subject_id=subject_id,
            limit=10,
            category=category,
            unit_tag=unit_tag,
        )

        # ---------------------------------------------------------
        # 3. Reranking
        # ---------------------------------------------------------

        reranked_chunks = reranker.rerank(
            expanded_query,
            raw_matches,
        )[:limit]

        # ---------------------------------------------------------
        # 4. Prevent hallucination when no evidence exists
        # ---------------------------------------------------------

        if not reranked_chunks:
            return (
                "Confidence: Low. Insufficient evidence in uploaded "
                "documents to answer."
            ), []

        # ---------------------------------------------------------
        # 5. Build grounded context
        # ---------------------------------------------------------

        formatted_context = self._format_context(reranked_chunks)

        # ---------------------------------------------------------
        # 6. Generate answer using Ollama/local LLM
        # ---------------------------------------------------------

        try:
            answer = await self._generate_llm_response(
                query=query,
                expanded_query=expanded_query,
                context=formatted_context,
            )

            return answer, reranked_chunks

        except Exception as exc:
            # Do not silently return a fake AI answer.
            # Surface a clear error so the problem can be diagnosed.
            print(f"Local LLM generation failed: {exc}")

            raise RuntimeError(
                "The local LLM could not generate a response. "
                "Make sure Ollama is running and the configured model "
                f"'{settings.LLM_MODEL}' is available."
            ) from exc


# Singleton instance
rag_engine = RAGEngine()