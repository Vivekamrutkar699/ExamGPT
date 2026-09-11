import asyncio
import uuid

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.services.pyq import pyq_service


async def test_pyq_analytics_flow():
    print("Beginning PYQ Ingestion & Analytics E2E Test...")
    
    async with SessionLocal() as db:
        # 1. Setup temporary course Subject & User
        test_user = User(
            email=f"pyqer_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="PYQ Analyst",
            role="admin"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-PYQ-{uuid.uuid4().hex[:4].upper()}",
            name="Testing PYQ Ingestion Pipeline",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)

        # 2. Raw PYQ examination text stream
        # Includes Q1 and Q3 which are semantically similar loaders/linking questions
        raw_paper = (
            "SAVITRIBAI PHULE PUNE UNIVERSITY EXAM PAPERS\n"
            "CS-334: SYSTEM PROGRAMMING\n\n"
            "Q1. Explain dynamic linking loader stages in detail. [10M]\n"
            "Q2. Briefly describe compile time hazards. [5 Marks]\n"
            "Q3. Explain dynamic linking loader stages. [10M]\n"
        )

        # 3. Ingest text
        print("Ingesting raw examination paper text stream...")
        questions = await pyq_service.ingest_pyq_text(
            db=db,
            subject_id=test_subject.id,
            text=raw_paper
        )
        
        # Verify deduplication grouped the similar loader questions together
        # We expect 2 unique questions total, with Q1 occurrence = 2
        print(f"Ingestion parsed {len(questions)} lines.")
        
        # 4. Fetch aggregations
        print("Fetching PYQ analytics calculations...")
        analytics = await pyq_service.get_subject_analytics(db, subject_id=test_subject.id)
        
        # Assertions
        assert analytics.total_pyqs == 2
        assert "10M" in analytics.marks_distribution
        assert "5M" in analytics.marks_distribution
        assert analytics.marks_distribution["10M"] == 1
        assert analytics.marks_distribution["5M"] == 1
        
        # Best repeated question check
        best_repeated = analytics.top_repeated[0]
        assert best_repeated.occurrences == 2
        assert "loader" in best_repeated.text.lower()
        print("OK: Semantic deduplication and repetition occurrence count verified.")
        print(f"OK: Top repeated: '{best_repeated.text}' (Occurrences: {best_repeated.occurrences})")
        print(f"OK: Marks distribution: {analytics.marks_distribution}")
        
        # Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("Database entities cleared.")
        print("PYQ Ingestion & Analytics E2E Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_pyq_analytics_flow())
