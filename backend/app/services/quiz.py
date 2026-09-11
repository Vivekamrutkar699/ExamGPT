import uuid
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Quiz
from app.schemas.quiz import QuizSubmission, QuizGradeOut
from app.repositories.quiz import quiz_repository
from app.rag.engine import rag_engine


class QuizService:
    """
    Coordinates RAG-grounded quiz generation and submission grading.
    """

    def _generate_mock_questions(self, quiz_type: str) -> List[Dict[str, Any]]:
        """Generates standard engineering mockup questions for testing."""
        if quiz_type == "MCQ":
            return [
                {
                    "id": "mcq_1",
                    "question": "Which of the following describes the function of a linker?",
                    "choices": {
                        "A": "Copy binaries into RAM memory",
                        "B": "Combine object files into a single executable",
                        "C": "Generate assembly language code",
                        "D": "Direct CPU bus structures"
                    },
                    "correct_answer": "B",
                    "explanation": "Linkers bind independent compiled object modules into a single, cohesive executable binary."
                },
                {
                    "id": "mcq_2",
                    "question": "Dynamic linking resolves library references at which stage?",
                    "choices": {
                        "A": "Compilation",
                        "B": "Runtime / Execution",
                        "C": "Assembly",
                        "D": "Preprocessing"
                    },
                    "correct_answer": "B",
                    "explanation": "Dynamic linking defer resolving symbols until load/run time, allowing dll binaries sharing."
                },
                {
                    "id": "mcq_3",
                    "question": "What function does the loader perform?",
                    "choices": {
                        "A": "Translate code to tokens",
                        "B": "Link symbols dynamically",
                        "C": "Load program segments into memory allocations",
                        "D": "Execute register assignments"
                    },
                    "correct_answer": "C",
                    "explanation": "Loaders copy compiled binary instructions into physical memory pages to begin CPU executions."
                }
            ]
        else:
            return [
                {
                    "id": "short_1",
                    "question": "Differentiate between static and dynamic linking in detail.",
                    "ideal_keywords": ["memory size", "runtime", "sharing", "symbols"],
                    "marks": 5
                },
                {
                    "id": "short_2",
                    "question": "Explain the basic stages in compiler design logic flow.",
                    "ideal_keywords": ["lexical", "parsing", "syntax", "intermediate"],
                    "marks": 5
                }
            ]

    async def generate_quiz(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        title: str,
        quiz_type: str = "MCQ",
        unit_tag: Optional[str] = None
    ) -> Quiz:
        """
        Retrieves context chunks from notes linked to subject,
        generates structured question objects, and saves them.
        """
        # Call RAG engine to grab context for question synthesis
        answer, contexts = await rag_engine.get_grounded_answer(
            db=db,
            query="find main system architectures, loaders, compiler definitions, and linker stages",
            subject_id=subject_id,
            unit_tag=unit_tag,
            limit=3
        )

        # Synthesis questions list using custom mock generation fallback
        # Can be expanded to call LLM dynamically in future phases
        questions = self._generate_mock_questions(quiz_type)

        questions_data = {
            "questions": questions
        }

        return await quiz_repository.create_quiz(
            db=db,
            subject_id=subject_id,
            title=title,
            quiz_type=quiz_type,
            questions_data=questions_data
        )

    async def grade_quiz(
        self,
        db: AsyncSession,
        quiz_id: uuid.UUID,
        submission: QuizSubmission
    ) -> QuizGradeOut:
        """
        Compares submitted options with correct answer keys,
        calculates scoring weights, and maps detailed feedback.
        """
        quiz = await quiz_repository.get_by_id(db, quiz_id=quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz worksheet not found."
            )

        questions = quiz.questions_data.get("questions", [])
        
        correct_count = 0
        feedback_list = []

        for q in questions:
            qid = q["id"]
            user_ans = submission.answers.get(qid, "").strip().upper()
            correct_ans = q.get("correct_answer", "").strip().upper()
            
            is_correct = False
            
            if quiz.quiz_type == "MCQ":
                is_correct = (user_ans == correct_ans)
                if is_correct:
                    correct_count += 1
                    
                feedback_list.append({
                    "question_id": qid,
                    "question": q["question"],
                    "user_answer": user_ans,
                    "correct_answer": correct_ans,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", "No explanation available.")
                })
            else:
                # Lexical feedback for short/long answers comparing user input with ideal keywords
                user_ans_lower = user_ans.lower()
                matched_keywords = [
                    kw for kw in q.get("ideal_keywords", [])
                    if kw.lower() in user_ans_lower
                ]
                keyword_ratio = len(matched_keywords) / len(q.get("ideal_keywords", [1]))
                is_correct = (keyword_ratio >= 0.5)
                if is_correct:
                    correct_count += 1

                feedback_list.append({
                    "question_id": qid,
                    "question": q["question"],
                    "user_answer": user_ans,
                    "matched_keywords": matched_keywords,
                    "score_ratio": keyword_ratio,
                    "is_correct": is_correct,
                    "explanation": f"Ideal answer keywords: {', '.join(q.get('ideal_keywords', []))}"
                })

        total_questions = len(questions)
        score_percent = float(correct_count / total_questions) * 100.0 if total_questions > 0 else 0.0

        return QuizGradeOut(
            quiz_id=quiz.id,
            total_questions=total_questions,
            correct_answers=correct_count,
            score_percent=round(score_percent, 1),
            feedback=feedback_list
        )


# Singleton service instance
quiz_service = QuizService()
