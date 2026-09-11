import uuid
import re
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answers_evaluation import AnswersEvaluation
from app.models.question import Question
from app.repositories.evaluation import evaluation_repository
from app.rag.engine import rag_engine


class EvaluationService:
    """
    Evaluates student long-form answers: compares submissions against
    grounded RAG contexts, scores marks, and compiles improvement points.
    """

    def _extract_nouns(self, text: str) -> set[str]:
        """Convert a text block to lowercase tokens longer than 4 chars."""
        words = re.findall(r'\b\w{4,}\b', text.lower())
        stopwords = {
            "about", "would", "their", "there", "these", "those", "which",
            "where", "after", "before", "under", "above", "while", "during"
        }
        return set(w for w in words if w not in stopwords)

    async def evaluate_student_answer(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        user_submitted_answer: str
    ) -> AnswersEvaluation:
        """
        Grades an essay submission against RAG reference study slides/notes.
        """
        # 1. Fetch Question meta configurations
        question = await db.get(Question, question_id)
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question record not found."
            )

        max_marks = float(question.marks_weight)

        # 2. Retrieve relevant reference chunks using RAG Engine
        answer, contexts = await rag_engine.get_grounded_answer(
            db=db,
            query=question.text,
            subject_id=question.subject_id,
            limit=3
        )

        if not contexts:
            # Fallback evaluation if no notes are indexed in subject vault yet
            estimated_marks = round(max_marks * 0.5, 1)
            feedback = (
                "Evaluation completed under offline fallback mode. "
                "No reference slides/notes found in subject vault to verify answer."
            )
            improvement = {
                "missing_keywords": [],
                "structural_gaps": ["Upload study syllabus/notes to unlock full keyword checklists evaluations."]
            }
            return await evaluation_repository.create_evaluation(
                db=db,
                user_id=user_id,
                question_id=question_id,
                user_submitted_answer=user_submitted_answer,
                feedback=feedback,
                estimated_marks=estimated_marks,
                max_marks=max_marks,
                improvement_points=improvement
            )

        # 3. Analyze Keyword coverage ratios
        context_text = " ".join([c["content"] for c in contexts])
        context_words = self._extract_nouns(context_text)
        answer_words = self._extract_nouns(user_submitted_answer)

        # Limit vocabulary to top nouns present in study material
        matched_keywords = context_words.intersection(answer_words)
        missing_keywords = list(context_words.difference(answer_words))[:5]

        coverage_ratio = len(matched_keywords) / len(context_words) if context_words else 0.0

        # 4. Apply length penalty heuristics
        char_count = len(user_submitted_answer)
        length_multiplier = 1.0
        structural_gaps = []

        if char_count < 100:
            length_multiplier = 0.3
            structural_gaps.append("Answer is extremely brief. SPPU answers require structural detail.")
        elif char_count < 250:
            length_multiplier = 0.6
            structural_gaps.append("Answer is short. Expand explanation blocks with system definitions.")
        elif char_count > 600:
            length_multiplier = 1.0
        
        # 5. Calculate final score
        # Marks = Coverage * MaxMarks * LengthMultiplier
        calculated_score = coverage_ratio * max_marks * length_multiplier
        # Ensure a minimum score if they wrote something reasonable
        if char_count > 250 and calculated_score < (max_marks * 0.4):
            calculated_score = max_marks * 0.45

        # Format and round
        estimated_marks = round(min(max_marks, max(0.0, calculated_score)), 1)

        # 6. Formulate feedback text
        score_percent = (estimated_marks / max_marks) * 100.0
        if score_percent >= 80.0:
            feedback = "Excellent! You covered almost all key syllabus elements and vocabulary terms."
        elif score_percent >= 50.0:
            feedback = "Good response, but missing some key concepts. Check DLL offsets or symbol resolving."
        else:
            feedback = "Insufficient detail. The answer lacks required technical keywords and structures."

        improvement = {
            "missing_keywords": missing_keywords,
            "structural_gaps": structural_gaps
        }

        # 7. Commit evaluation row
        return await evaluation_repository.create_evaluation(
            db=db,
            user_id=user_id,
            question_id=question_id,
            user_submitted_answer=user_submitted_answer,
            feedback=feedback,
            estimated_marks=estimated_marks,
            max_marks=max_marks,
            improvement_points=improvement
        )


# Singleton service instance
evaluation_service = EvaluationService()
