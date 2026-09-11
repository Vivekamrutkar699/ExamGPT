import asyncio
import uuid
from unittest.mock import patch

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.services.processing import processing_service
from app.services.quiz import quiz_service
from app.repositories.quiz import quiz_repository
from app.schemas.quiz import QuizSubmission


async def test_quiz_generator_flow():
    print("Beginning Quiz Generator E2E Integration Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"quizzer_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Quiz Coordinator",
            role="admin"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-QUIZ-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Quiz Synthesizer",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        # 2. Ingest notes
        test_doc = Document(
            subject_id=test_subject.id,
            name="quiz_syllabus.pdf",
            storage_path="mock_uploads/quiz_syllabus.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        mock_extracted_pages = [
            {"page": 1, "text": "UNIT 1: LOADERS. Loaders allocation memory.", "tables": []}
        ]

        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        print("Syllabus document indexed. Generating dynamic MCQ quiz...")

        # 3. Generate quiz
        quiz = await quiz_service.generate_quiz(
            db=db,
            subject_id=test_subject.id,
            title="Systems Design Quiz",
            quiz_type="MCQ"
        )
        
        assert quiz.subject_id == test_subject.id
        assert quiz.quiz_type == "MCQ"
        assert len(quiz.questions_data["questions"]) == 3
        print("OK: Dynamic quiz created with 3 questions.")

        # 4. Check that answers are stored in database record
        questions = quiz.questions_data["questions"]
        assert "correct_answer" in questions[0]
        assert "explanation" in questions[0]

        # 5. Grade submission (2 correct, 1 incorrect)
        submission = QuizSubmission(
            answers={
                "mcq_1": "B",  # correct
                "mcq_2": "B",  # correct
                "mcq_3": "A"   # incorrect (correct is C)
            }
        )
        
        print("Grading quiz submission payload...")
        grade = await quiz_service.grade_quiz(db, quiz_id=quiz.id, submission=submission)
        
        assert grade.total_questions == 3
        assert grade.correct_answers == 2
        assert grade.score_percent == 66.7
        assert grade.feedback[0]["is_correct"] is True
        assert grade.feedback[2]["is_correct"] is False
        print(f"OK: Submission graded. Score: {grade.score_percent}%, Correct: {grade.correct_answers}/3")

        # 6. Delete quiz
        await quiz_repository.delete_quiz(db, quiz.id)
        
        # Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Quiz Generator E2E Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_quiz_generator_flow())
