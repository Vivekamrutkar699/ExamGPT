import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal
from app.models.pyq_topic import PYQPaper, PYQQuestionOccurrence
from app.models.subject import Subject
from app.models.user import User
from app.services.pyq_topic_ingestion import PYQTopicIngestionService


class FakeEncoder:
    model_version = "fake-v1"

    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]


class TopicIngestionSQLiteTests(unittest.TestCase):
    def test_exact_occurrences_and_paper_idempotency(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        async with SessionLocal() as db:
            user = User(email=f"topic_{uuid.uuid4().hex}@test.local", hashed_password="x", full_name="Topic", role="admin")
            subject = Subject(code=f"TOPIC-{uuid.uuid4().hex[:8]}", name="Topic", semester=1, branch="Test")
            db.add_all([user, subject]); await db.commit(); await db.refresh(subject)
            try:
                service = PYQTopicIngestionService(encoder=FakeEncoder())
                parsed = [{"text": "Explain dynamic linking.", "marks_weight": 5, "question_number": "Q1"}]
                first = await service.ingest(db, subject.id, parsed, "Q1. Explain dynamic linking. [5M]")
                second = await service.ingest(db, subject.id, parsed, "Q1. Explain dynamic linking. [5M]")
                third = await service.ingest(
                    db,
                    subject.id,
                    [{"text": "Explain dynamic linking.", "marks_weight": 10, "question_number": "Q1"}],
                    "Q1. Explain dynamic linking. [10M]",
                )
                self.assertEqual(first[0].id, second[0].id)
                self.assertEqual(first[0].id, third[0].id)
                papers = (await db.execute(__import__("sqlalchemy").select(PYQPaper).where(PYQPaper.subject_id == subject.id))).scalars().all()
                occurrences = (await db.execute(__import__("sqlalchemy").select(PYQQuestionOccurrence).join(PYQPaper).where(PYQPaper.subject_id == subject.id))).scalars().all()
                self.assertEqual(len(papers), 2)
                self.assertEqual(sorted(item.marks_weight for item in occurrences), [5, 10])
            finally:
                await db.delete(subject); await db.delete(user); await db.commit()


if __name__ == "__main__":
    unittest.main()
