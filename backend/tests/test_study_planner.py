import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.document import Document
from app.services.processing import processing_service
from app.services.study_plan import study_plan_service
from app.repositories.study_plan import study_plan_repository


async def test_study_planner_flow():
    print("Beginning Study Planner E2E Integration Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"planner_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Study Plan Director",
            role="student"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-PLAN-{uuid.uuid4().hex[:4].upper()}",
            name="Testing Study Planner Algorithms",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)
        
        # 2. Ingest notes with specific units
        test_doc = Document(
            subject_id=test_subject.id,
            name="planner_syllabus.pdf",
            storage_path="mock_uploads/planner_syllabus.pdf",
            file_type="pdf",
            category="notes",
            processing_status="pending",
            uploaded_by=test_user.id
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)

        mock_extracted_pages = [
            {"page": 1, "text": "UNIT 1: LOADERS. Loaders are essential.", "tables": []},
            {"page": 2, "text": "UNIT II: COMPILERS. Compilers parse tokens.", "tables": []},
            {"page": 3, "text": "UNIT 3: LINKERS. Linkers link libs.", "tables": []}
        ]

        with patch("app.document_processing.parser.document_parser.extract_text", return_value=mock_extracted_pages):
            await processing_service.process_document(db, test_doc.id)
            
        print("Syllabus documents indexed. Generating study schedule...")

        # 3. Generate study plan
        plan = await study_plan_service.generate_study_plan(
            db=db,
            user_id=test_user.id,
            subject_id=test_subject.id,
            days_duration=30
        )
        
        assert plan.user_id == test_user.id
        assert plan.subject_id == test_subject.id
        assert plan.schedule["progress_percent"] == 0.0
        
        # Check checkpoints are generated
        # Based on Units 1, 2, 3 detected in pages
        checkpoints = plan.schedule["checkpoints"]
        assert len(checkpoints) == 3
        assert checkpoints[0]["unit_tag"] == "Unit 1"
        assert checkpoints[1]["unit_tag"] == "Unit 2"
        assert checkpoints[2]["unit_tag"] == "Unit 3"
        print("OK: Study plan successfully generated and divided among 3 units.")

        # 4. Toggle progress checkpoint and check recalculations
        print("Toggling Unit 1 checkpoint to completed...")
        updated_plan = await study_plan_service.update_checkpoint(
            db=db,
            plan_id=plan.id,
            user_id=test_user.id,
            item_id="unit_chk_1",
            completed=True
        )
        
        # 1 completed out of 3 = 33.3% progress
        assert updated_plan.schedule["progress_percent"] == 33.3
        assert updated_plan.schedule["checkpoints"][0]["completed"] is True
        print(f"OK: Progress recalculated correctly. Updated progress: {updated_plan.schedule['progress_percent']}%")
        
        # 5. Delete plan
        await study_plan_repository.delete_plan(db, plan.id)
        
        # Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("Study Planner E2E Integration Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_study_planner_flow())
