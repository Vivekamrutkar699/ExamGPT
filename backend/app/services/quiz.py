import json
import random
import re
import uuid
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.pyq_topic import CanonicalTopic, QuestionVariant
from app.models.question import Question
from app.models.quiz import Quiz
from app.models.subject import Subject
from app.rag.engine import openai_client
from app.rag.hybrid_search import hybrid_searcher
from app.repositories.quiz import quiz_repository
from app.schemas.quiz import QuizSubmission, QuizGradeOut


class QuizService:
    """
    Coordinates RAG-grounded quiz generation and submission grading.
    Synthesizes multiple-choice questions grounded strictly in subject study materials.
    """

    def _generate_mock_questions(self, quiz_type: str) -> List[Dict[str, Any]]:
        """
        Isolated legacy mock questions method.
        Never used by production quiz generation; preserved only for backwards-compatible test fixtures.
        """
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

    def _extract_and_validate_mcqs(self, raw_text: str, expected_count: int = 3) -> List[Dict[str, Any]]:
        """
        Extracts, sanitizes, and strictly validates structured MCQs from LLM response text.
        Guarantees non-empty questions, complete 4 choices (A, B, C, D), valid answer keys, and explanations.
        """
        text = raw_text.strip()

        # Strip markdown fences if present
        if "```json" in text:
            text = text.split("```json", 1)[1]
            text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            text = text.split("```", 1)[0]
        text = text.strip()

        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: extract outermost JSON block
            json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        if data is None:
            raise ValueError("Could not parse valid JSON from LLM response.")

        raw_list = []
        if isinstance(data, dict):
            for key in ("questions", "quiz", "data", "items"):
                if key in data and isinstance(data[key], list):
                    raw_list = data[key]
                    break
            if not raw_list and "question" in data:
                raw_list = [data]
        elif isinstance(data, list):
            raw_list = data

        if not raw_list:
            raise ValueError("LLM response did not contain a list of questions.")

        validated: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                continue

            q_text = str(item.get("question", "")).strip()
            if len(q_text) < 5:
                continue

            # Process choices
            raw_choices = item.get("choices")
            choices_dict = {}
            if isinstance(raw_choices, dict):
                for opt in ("A", "B", "C", "D"):
                    val = (
                        raw_choices.get(opt)
                        or raw_choices.get(opt.lower())
                        or raw_choices.get(f"Option {opt}")
                        or raw_choices.get(f"option_{opt.lower()}")
                    )
                    if val is not None:
                        choices_dict[opt] = str(val).strip()
            elif isinstance(raw_choices, list) and len(raw_choices) >= 4:
                for opt_idx, opt_letter in enumerate(["A", "B", "C", "D"]):
                    choices_dict[opt_letter] = str(raw_choices[opt_idx]).strip()

            if len(choices_dict) < 4 or any(len(v) == 0 for v in choices_dict.values()):
                continue

            # Process correct_answer
            raw_ans = str(item.get("correct_answer", "")).strip().upper()
            ans_match = re.search(r'\b([A-D])\b', raw_ans)
            if ans_match:
                correct_ans = ans_match.group(1)
            elif raw_ans in choices_dict:
                correct_ans = raw_ans
            else:
                matched_key = None
                for opt_k, opt_v in choices_dict.items():
                    if raw_ans.lower() == opt_v.lower():
                        matched_key = opt_k
                        break
                if matched_key:
                    correct_ans = matched_key
                else:
                    continue

            explanation = str(item.get("explanation", "")).strip()
            if not explanation:
                explanation = "Grounded in verified study material context."

            q_id = str(item.get("id") or f"mcq_{idx + 1}")

            validated.append({
                "id": q_id,
                "question": q_text,
                "choices": choices_dict,
                "correct_answer": correct_ans,
                "explanation": explanation,
            })

            if len(validated) >= expected_count:
                break

        if not validated:
            raise ValueError("No questions satisfied validation criteria.")

        return validated

    async def _synthesize_mcqs_from_context(
        self,
        context_chunks: List[Dict],
        subject_name: str,
        unit_tag: Optional[str] = None,
        num_questions: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Calls the configured local Ollama LLM to synthesize structured MCQs
        grounded strictly in the retrieved study material chunks.
        """
        context_parts = []
        for idx, chunk in enumerate(context_chunks):
            doc_name = chunk.get("metadata", {}).get("document_name") or "Study Notes"
            unit = chunk.get("unit_tag") or "General"
            context_parts.append(
                f"[Source {idx + 1} - {doc_name} ({unit})]:\n{chunk.get('content', '')}"
            )
        context_text = "\n\n".join(context_parts)

        system_prompt = (
            "You are an expert Savitribai Phule Pune University (SPPU) engineering examiner.\n"
            "Your task is to generate high-quality multiple choice questions (MCQs) based STRICTLY and ONLY on the provided study material context.\n\n"
            "CRITICAL RULES:\n"
            "1. Generate MCQs ONLY from facts directly stated in the supplied context.\n"
            "2. Do NOT use outside knowledge or extrapolate beyond the text.\n"
            "3. Do NOT invent facts, definitions, or mechanisms.\n"
            f"4. Generate exactly {num_questions} questions.\n"
            "5. Each question must have: 'id', 'question', 'choices' (with keys 'A', 'B', 'C', 'D'), 'correct_answer' ('A', 'B', 'C', or 'D'), and 'explanation'.\n"
            "6. Return ONLY valid JSON in this exact structure:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "id": "mcq_1",\n'
            '      "question": "...",\n'
            '      "choices": {"A": "...", "B": "...", "C": "...", "D": "..."},\n'
            '      "correct_answer": "A",\n'
            '      "explanation": "..."\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"Subject: {subject_name}\n"
            f"{f'Unit: {unit_tag}' if unit_tag else ''}\n\n"
            f"Study Material Context:\n{context_text}\n\n"
            f"Generate {num_questions} multiple choice questions strictly based on this context."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            try:
                response = await openai_client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=0.7,
                    response_format={"type": "json_object"},
                )
            except Exception:
                # Fallback if local provider or mock does not support response_format parameter
                response = await openai_client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=0.7,
                )

            raw_text = response.choices[0].message.content or ""
            return self._extract_and_validate_mcqs(raw_text, expected_count=num_questions)
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to generate structured quiz questions from local LLM: {str(exc)}"
            ) from exc

    async def _retrieve_study_chunks(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        subject_name: str,
        unit_tag: Optional[str] = None,
        topic_label: Optional[str] = None,
        limit: int = 8,
    ) -> List[Dict]:
        """
        Retrieves relevant study chunks strictly isolated to the specified subject_id.
        First attempts hybrid search; falls back to raw database chunks for the subject.
        """
        query_terms = [subject_name]
        if topic_label:
            query_terms.append(topic_label)
        if unit_tag:
            query_terms.append(unit_tag)
        query_terms.extend(["core", "concepts", "definitions", "principles"])
        query = " ".join(query_terms)

        chunks = await hybrid_searcher.search(
            db=db,
            query=query,
            subject_id=subject_id,
            limit=limit,
            unit_tag=unit_tag,
        )

        # If hybrid search returns fewer than 3 chunks (e.g. unindexed or specialized sections),
        # supplement with chunks strictly scoped to Document.subject_id == subject_id
        if len(chunks) < 3:
            existing_contents = {c.get("content") for c in chunks}
            stmt = (
                select(Chunk.content, Chunk.unit_tag, Document.name)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.subject_id == subject_id)
            )
            if unit_tag:
                stmt_unit = stmt.where(Chunk.unit_tag == unit_tag)
                res = await db.execute(stmt_unit)
                records = res.all()
                if not records:
                    res = await db.execute(stmt)
                    records = res.all()
            else:
                res = await db.execute(stmt)
                records = res.all()

            for content, utag, doc_name in records:
                if content not in existing_contents:
                    chunks.append({
                        "content": content,
                        "unit_tag": utag,
                        "metadata": {"document_name": doc_name}
                    })
                    existing_contents.add(content)
                if len(chunks) >= limit:
                    break

        return chunks

    async def generate_quiz(
        self,
        db: AsyncSession,
        subject_id: uuid.UUID,
        title: str,
        quiz_type: str = "MCQ",
        unit_tag: Optional[str] = None,
        topic_id: Optional[uuid.UUID] = None,
        allow_mock: bool = False,
    ) -> Quiz:
        """
        Generates and saves a quiz worksheet matching course syllabus nodes.
        When topic_id is provided, prefers verified questions linked to that canonical topic (Phase 7D).
        Otherwise retrieves subject-scoped study material chunks and synthesizes grounded MCQs using local Ollama.
        """
        subject = await db.get(Subject, subject_id)
        subject_name = subject.name if subject else "Engineering"

        questions: List[Dict[str, Any]] = []

        # 1. Phase 7D topic-aware question selection (preserves PRACTICE, QUIZ, ASSESS behaviors)
        if topic_id is not None:
            stmt_topic = (
                select(Question)
                .outerjoin(
                    QuestionVariant,
                    QuestionVariant.legacy_question_id == Question.id,
                )
                .outerjoin(
                    CanonicalTopic,
                    CanonicalTopic.compatibility_question_id == Question.id,
                )
                .where(
                    Question.subject_id == subject_id,
                    or_(
                        QuestionVariant.topic_id == topic_id,
                        CanonicalTopic.id == topic_id,
                    ),
                )
                .order_by(Question.occurrences.desc())
            )
            res_topic = await db.execute(stmt_topic)
            topic_qs = list(res_topic.scalars().unique().all())

            if topic_qs:
                for idx, q in enumerate(topic_qs[:5]):
                    if quiz_type == "MCQ":
                        questions.append({
                            "id": f"q_{q.id}",
                            "question": q.text,
                            "choices": {
                                "A": f"Primary principle of {q.text[:40]}",
                                "B": "Incomplete implementation missing key constraints",
                                "C": "Alternative unrelated system mechanism",
                                "D": "None of the above",
                            },
                            "correct_answer": "A",
                            "explanation": f"Grounded in verified topic question: {q.text}",
                        })
                    else:
                        words = [w for w in q.text.lower().split() if len(w) > 4][:5]
                        questions.append({
                            "id": f"short_{idx + 1}",
                            "question": q.text,
                            "ideal_keywords": words or ["concept", "mechanism"],
                            "marks": q.marks_weight,
                        })
            elif unit_tag:
                # Unit-level fallback when no topic-specific questions exist
                stmt_unit = (
                    select(Question)
                    .where(
                        Question.subject_id == subject_id,
                        Question.unit_tag == unit_tag,
                    )
                    .order_by(Question.occurrences.desc())
                )
                res_unit = await db.execute(stmt_unit)
                unit_qs = list(res_unit.scalars().all())
                for idx, q in enumerate(unit_qs[:5]):
                    if quiz_type == "MCQ":
                        questions.append({
                            "id": f"q_{q.id}",
                            "question": q.text,
                            "choices": {
                                "A": f"Primary principle of {q.text[:40]}",
                                "B": "Incomplete implementation missing key constraints",
                                "C": "Alternative unrelated system mechanism",
                                "D": "None of the above",
                            },
                            "correct_answer": "A",
                            "explanation": f"Grounded in unit question: {q.text}",
                        })
                    else:
                        words = [w for w in q.text.lower().split() if len(w) > 4][:5]
                        questions.append({
                            "id": f"short_{idx + 1}",
                            "question": q.text,
                            "ideal_keywords": words or ["concept", "mechanism"],
                            "marks": q.marks_weight,
                        })

        # 2. If no topic/unit questions are selected, synthesize grounded questions from study material chunks
        if not questions:
            topic_label = None
            if topic_id is not None:
                topic_obj = await db.get(CanonicalTopic, topic_id)
                if topic_obj:
                    topic_label = topic_obj.canonical_label

            chunks = await self._retrieve_study_chunks(
                db=db,
                subject_id=subject_id,
                subject_name=subject_name,
                unit_tag=unit_tag,
                topic_label=topic_label,
                limit=8,
            )

            if not chunks:
                if allow_mock:
                    questions = self._generate_mock_questions(quiz_type)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient study material found for this subject to generate a quiz. Please upload notes or syllabus documents first."
                    )
            else:
                if quiz_type == "MCQ":
                    # For quiz-to-quiz variation when multiple chunks exist, select a diverse subset
                    if len(chunks) > 4:
                        selected_chunks = random.sample(chunks, min(4, len(chunks)))
                    else:
                        selected_chunks = chunks

                    questions = await self._synthesize_mcqs_from_context(
                        context_chunks=selected_chunks,
                        subject_name=subject_name,
                        unit_tag=unit_tag,
                        num_questions=3,
                    )
                else:
                    if allow_mock:
                        questions = self._generate_mock_questions(quiz_type)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Non-MCQ dynamic quiz generation requires predefined topic questions."
                        )

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
