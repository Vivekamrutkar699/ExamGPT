import asyncio
import uuid
from unittest.mock import patch

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.models.question import Question
from app.services.processing import processing_service
from app.services.evaluation import evaluation_service
from app.repositories.evaluation import evaluation_repository


async def test_essay_evaluation_flow():
    print("Beginning Essay Answer Evaluation E2E Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"evaler_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Essay Grader Director",
            role="student"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-EVAL-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Essay Answer Evaluators",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        # 2. Ingest notes with key vocabulary
        test_doc = Document(
            subject_id=test_subject.id,
            name="eval_notes.pdf",
            storage_path="mock_uploads/eval_notes.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        mock_extracted_pages = [
            {"page": 1, "text": "UNIT 1: LOADERS. Loaders copy dynamic compiled libraries and program segments into physical memory allocations.", "tables": []}
        ]

        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        # 3. Create mock question to evaluate against
        test_question = Question(
            subject_id=test_subject.id,
            text="Explain the function of loaders in memory allocations.",
            marks_weight=10,
            unit_tag="Unit 1",
            is_pyq=True,
            occurrences=1
        )
        db.add(test_question)
        await db.commit()
        await db.refresh(test_question)
        print("Subject and Question registered. Submitting student essay answer...")

        # 4. Evaluate a solid answer (containing matched words)
        student_ans = "Loaders allocate memory space and copy dynamic compiled libraries and program segments into memory allocations."
        evaluation = await evaluation_service.evaluate_student_answer(
            db=db,
            user_id=test_user.id,
            question_id=test_question.id,
            user_submitted_answer=student_ans
        )
        
        assert evaluation.user_id == test_user.id
        assert evaluation.question_id == test_question.id
        assert evaluation.max_marks == 10.0
        assert evaluation.estimated_marks > 3.0  # verify matching keywords boost
        assert "loaders" in evaluation.user_submitted_answer.lower()
        print(f"OK: Evaluation complete. Score: {evaluation.estimated_marks}/10.0, Feedback: {evaluation.feedback}")
        
        # 5. Delete evaluation
        await evaluation_repository.delete_evaluation(db, evaluation.id)
        
        # Cleanup
        await db.delete(test_question)
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Essay Answer Evaluation E2E Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_essay_evaluation_flow())
