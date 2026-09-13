import json
import re
import uuid
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.answers_evaluation import AnswersEvaluation
from app.models.question import Question
from app.repositories.evaluation import evaluation_repository
from app.rag.engine import rag_engine


class EvaluationService:
    """
    Evaluates student answers against grounded study-material context.

    The evaluator uses:
    1. RAG to retrieve question-specific reference material.
    2. Local Ollama LLM to assess the answer against that material.
    3. A deterministic fallback if the LLM is unavailable.
    """

    def __init__(self):
        self.llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "ollama",
            base_url=settings.OPENAI_API_BASE or "http://localhost:11434/v1",
        )

    def _extract_nouns(self, text: str) -> set[str]:
        """
        Extract useful technical tokens for deterministic fallback scoring.
        """
        words = re.findall(r"\b\w{4,}\b", text.lower())

        stopwords = {
            "about",
            "would",
            "their",
            "there",
            "these",
            "those",
            "which",
            "where",
            "after",
            "before",
            "under",
            "above",
            "while",
            "during",
            "should",
            "could",
            "also",
            "than",
            "that",
            "this",
            "with",
            "from",
            "have",
            "been",
            "into",
            "when",
            "what",
            "such",
            "more",
            "very",
        }

        return {
            word
            for word in words
            if word not in stopwords
        }

    def _build_reference_context(
        self,
        contexts: List[Dict[str, Any]],
    ) -> str:
        """
        Build a compact reference context for the evaluator.
        """

        parts = []

        for index, context in enumerate(contexts, start=1):
            document_name = (
                context.get("document_name")
                or context.get("filename")
                or "Study Material"
            )

            page = context.get("page") or context.get("page_number") or "N/A"

            content = context.get("content", "").strip()

            if not content:
                continue

            parts.append(
                f"[Reference {index}]\n"
                f"Document: {document_name}\n"
                f"Page: {page}\n"
                f"Content:\n{content}"
            )

        return "\n\n".join(parts)

    async def _llm_evaluate(
        self,
        question: str,
        student_answer: str,
        reference_context: str,
        max_marks: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Ask the local LLM to evaluate the student's answer.

        Returns structured JSON or None if the LLM cannot provide
        a valid response.
        """

        system_prompt = """
You are an engineering examination answer evaluator.

Your task is to evaluate a student's answer against the provided
question and retrieved university study material.

IMPORTANT RULES:

1. Evaluate ONLY against the provided study material.
2. Do not use unrelated general knowledge.
3. Do not invent concepts that are not supported by the references.
4. Do not penalize the student for not using exact wording.
5. Focus on conceptual coverage, technical correctness, and answer completeness.
6. The maximum marks are provided by the question.
7. Give a conservative score when the answer contains insufficient evidence.
8. Identify missing concepts only when those concepts are actually present
   or clearly supported in the reference material.
9. Do not mention concepts from unrelated subjects.
10. Return ONLY valid JSON.

Required JSON format:

{
  "estimated_marks": 0.0,
  "feedback": "Short explanation of the student's performance.",
  "missing_concepts": [
    "concept 1",
    "concept 2"
  ],
  "strengths": [
    "strength 1"
  ],
  "structural_gaps": [
    "gap 1"
  ]
}

estimated_marks must be between 0 and the maximum marks.
Keep feedback concise and examination-oriented.
"""

        user_prompt = f"""
QUESTION:
{question}

MAXIMUM MARKS:
{max_marks}

STUDENT ANSWER:
{student_answer}

RETRIEVED STUDY MATERIAL:
{reference_context}

Evaluate the student's answer using ONLY the retrieved study material.
"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0.1,
                max_tokens=600,
            )

            content = response.choices[0].message.content

            if not content:
                return None

            content = content.strip()

            # Handle accidental Markdown JSON fences.
            if content.startswith("```"):
                content = re.sub(
                    r"^```(?:json)?\s*",
                    "",
                    content,
                )
                content = re.sub(
                    r"\s*```$",
                    "",
                    content,
                )

            result = json.loads(content)

            estimated_marks = float(
                result.get("estimated_marks", 0.0)
            )

            estimated_marks = max(
                0.0,
                min(max_marks, estimated_marks),
            )

            return {
                "estimated_marks": round(
                    estimated_marks,
                    1,
                ),
                "feedback": str(
                    result.get(
                        "feedback",
                        "Answer evaluated against the retrieved study material.",
                    )
                ),
                "missing_concepts": list(
                    result.get("missing_concepts", [])
                )[:5],
                "strengths": list(
                    result.get("strengths", [])
                )[:5],
                "structural_gaps": list(
                    result.get("structural_gaps", [])
                )[:5],
            }

        except Exception:
            return None

    def _fallback_evaluate(
        self,
        question: str,
        student_answer: str,
        contexts: List[Dict[str, Any]],
        max_marks: float,
    ) -> Dict[str, Any]:
        """
        Deterministic fallback evaluator.

        This is intentionally conservative and only compares vocabulary
        from the retrieved references with the student's answer.
        """

        context_text = " ".join(
            context.get("content", "")
            for context in contexts
        )

        context_words = self._extract_nouns(
            context_text
        )

        answer_words = self._extract_nouns(
            student_answer
        )

        if not context_words:
            return {
                "estimated_marks": round(
                    max_marks * 0.5,
                    1,
                ),
                "feedback": (
                    "Evaluation completed using fallback mode. "
                    "The retrieved study material did not provide "
                    "enough structured reference information."
                ),
                "missing_concepts": [],
                "strengths": [],
                "structural_gaps": [],
            }

        matched_keywords = (
            context_words.intersection(answer_words)
        )

        coverage_ratio = (
            len(matched_keywords) / len(context_words)
            if context_words
            else 0.0
        )

        char_count = len(student_answer.strip())

        if char_count < 100:
            length_multiplier = 0.35
            structural_gaps = [
                "Answer is very brief.",
                "Add technical explanation and relevant stages or components.",
            ]

        elif char_count < 250:
            length_multiplier = 0.60
            structural_gaps = [
                "Answer needs more technical detail.",
            ]

        else:
            length_multiplier = 1.0
            structural_gaps = []

        calculated_score = (
            coverage_ratio
            * max_marks
            * length_multiplier
        )

        estimated_marks = round(
            min(
                max_marks,
                max(0.0, calculated_score),
            ),
            1,
        )

        score_percent = (
            estimated_marks / max_marks
        ) * 100.0 if max_marks > 0 else 0.0

        if score_percent >= 80:
            feedback = (
                "Strong answer with good coverage of the "
                "retrieved study material."
            )
        elif score_percent >= 50:
            feedback = (
                "Reasonable answer, but additional technical "
                "details from the study material are needed."
            )
        else:
            feedback = (
                "The answer provides limited coverage of the "
                "key concepts in the retrieved study material."
            )

        missing_concepts = [
            word
            for word in context_words
            if word not in answer_words
        ][:5]

        strengths = list(
            matched_keywords
        )[:5]

        return {
            "estimated_marks": estimated_marks,
            "feedback": feedback,
            "missing_concepts": missing_concepts,
            "strengths": strengths,
            "structural_gaps": structural_gaps,
        }

    async def evaluate_student_answer(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        user_submitted_answer: str,
    ) -> AnswersEvaluation:
        """
        Evaluate a student's long-form answer using grounded
        study-material context.
        """

        # ---------------------------------------------------------
        # 1. Fetch question
        # ---------------------------------------------------------
        question = await db.get(
            Question,
            question_id,
        )

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question record not found.",
            )

        max_marks = float(
            question.marks_weight
        )

        # ---------------------------------------------------------
        # 2. Retrieve question-specific reference material
        # ---------------------------------------------------------
        answer, contexts = await rag_engine.get_grounded_answer(
            db=db,
            query=question.text,
            subject_id=question.subject_id,
            limit=5,
        )

        # ---------------------------------------------------------
        # 3. No reference material
        # ---------------------------------------------------------
        if not contexts:
            estimated_marks = round(
                max_marks * 0.5,
                1,
            )

            feedback = (
                "Evaluation completed in fallback mode. "
                "No relevant study material was found in the "
                "subject vault, so the answer could not be fully "
                "verified against course material."
            )

            improvement = {
                "missing_concepts": [],
                "strengths": [],
                "structural_gaps": [
                    "Upload relevant study material to enable "
                    "grounded answer evaluation."
                ],
            }

            return await evaluation_repository.create_evaluation(
                db=db,
                user_id=user_id,
                question_id=question_id,
                user_submitted_answer=user_submitted_answer,
                feedback=feedback,
                estimated_marks=estimated_marks,
                max_marks=max_marks,
                improvement_points=improvement,
            )

        # ---------------------------------------------------------
        # 4. Build grounded evaluation context
        # ---------------------------------------------------------
        reference_context = self._build_reference_context(
            contexts
        )

        # ---------------------------------------------------------
        # 5. Evaluate using local Ollama
        # ---------------------------------------------------------
        llm_result = await self._llm_evaluate(
            question=question.text,
            student_answer=user_submitted_answer,
            reference_context=reference_context,
            max_marks=max_marks,
        )

        # ---------------------------------------------------------
        # 6. Deterministic fallback
        # ---------------------------------------------------------
        if llm_result is None:
            evaluation_result = self._fallback_evaluate(
                question=question.text,
                student_answer=user_submitted_answer,
                contexts=contexts,
                max_marks=max_marks,
            )
        else:
            evaluation_result = llm_result

        # ---------------------------------------------------------
        # 7. Prepare stored feedback
        # ---------------------------------------------------------
        improvement = {
            "missing_concepts": evaluation_result.get(
                "missing_concepts",
                [],
            ),
            "strengths": evaluation_result.get(
                "strengths",
                [],
            ),
            "structural_gaps": evaluation_result.get(
                "structural_gaps",
                [],
            ),
        }

        # ---------------------------------------------------------
        # 8. Store evaluation
        # ---------------------------------------------------------
        return await evaluation_repository.create_evaluation(
            db=db,
            user_id=user_id,
            question_id=question_id,
            user_submitted_answer=user_submitted_answer,
            feedback=evaluation_result["feedback"],
            estimated_marks=evaluation_result["estimated_marks"],
            max_marks=max_marks,
            improvement_points=improvement,
        )


# Singleton service instance.
evaluation_service = EvaluationService()