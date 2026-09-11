import asyncio
import uuid
from unittest.mock import patch

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.models.question import Question
from app.models.answers_evaluation import AnswersEvaluation
from app.services.processing import processing_service
from app.services.study_plan import study_plan_service
from app.services.analytics import analytics_service


async def test_analytics_dashboard_flow():
    print("Beginning Analytics Dashboard E2E Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"analyst_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Analytics Director",
            role="student"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-ANLY-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Analytics Aggregation",
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
            name="analytics_notes.pdf",
            storage_path="mock_uploads/analytics_notes.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        mock_extracted_pages = [
            {"page": 1, "text": "UNIT 1: LOADERS. Loaders copy program segments.", "tables": []},
            {"page": 2, "text": "UNIT 2: COMPILERS. Compilers compile code.", "tables": []}
        ]

        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        # 3. Create active study plan and check progress
        plan = await study_plan_service.generate_study_plan(
            db=db,
            user_id=test_user.id,
            subject_id=test_subject.id,
            days_duration=30
        )
        # Toggle checkpoint (1 out of 2 units complete = 50.0%)
        await study_plan_service.update_checkpoint(
            db=db,
            plan_id=plan.id,
            user_id=test_user.id,
            item_id="unit_chk_1",
            completed=True
        )

        # 4. Insert low-scoring essay evaluation under Unit 2 to test weak areas calculations
        q_unit2 = Question(
            subject_id=test_subject.id,
            text="Explain compiler frontend syntax structures.",
            marks_weight=10,
            unit_tag="Unit 2",
            is_pyq=True,
            occurrences=1
        )
        db.add(q_unit2)
        await db.commit()
        await db.refresh(q_unit2)

        low_eval = AnswersEvaluation(
            user_id=test_user.id,
            question_id=q_unit2.id,
            user_submitted_answer="Compilers compile things.",
            feedback="Insufficient detail.",
            estimated_marks=3.0,
            max_marks=10.0,
            improvement_points={"gaps": ["Lacks parsing phase detail."]}
        )
        db.add(low_eval)
        await db.commit()
        await db.refresh(low_eval)

        print("Dashboard contexts indexed. Retrieving aggregate report...")

        # 5. Retrieve Analytics Report
        report = await analytics_service.get_subject_analytics_report(
            db=db,
            user_id=test_user.id,
            subject_id=test_subject.id
        )
        
        assert report.subject_id == test_subject.id
        assert report.study_progress == 50.0
        assert report.total_essays_evaluated == 1
        assert report.average_essay_score == 30.0
        assert "Unit 2" in report.weak_units  # Unit 2 scored 30.0% which is < 60.0%
        print(f"OK: Aggregated progress: {report.study_progress}%, Essays Average: {report.average_essay_score}%")
        print(f"OK: Weak units flagged: {report.weak_units}")

        # 6. Cleanup
        await db.delete(low_eval)
        await db.delete(q_unit2)
        await db.delete(plan)
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Analytics Dashboard E2E Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_analytics_dashboard_flow())
