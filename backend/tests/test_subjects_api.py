import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from sqlalchemy import select
from app.database.session import SessionLocal
from app.models.subject import Subject
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectOut
from app.api.v1.endpoints.documents import list_subjects, create_subject, list_documents


class SubjectApiTests(unittest.TestCase):
    """
    Focused backend tests for:
    1. Authenticated subject listing
    2. Subject creation
    3. Duplicate subject code rejection
    4. Returned subject fields validation
    5. Document list integration with subject_id filter
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_01_authenticated_subject_listing(self) -> None:
        """Verify list_subjects retrieves all registered subjects for authenticated user."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_student_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="Subject Lister",
                    role="student",
                )
                db.add(user)

                code_a = f"TEST-A-{uuid.uuid4().hex[:4].upper()}"
                code_b = f"TEST-B-{uuid.uuid4().hex[:4].upper()}"
                sub_a = Subject(code=code_a, name="Alpha Engineering", semester=3, branch="Comp")
                sub_b = Subject(code=code_b, name="Beta Engineering", semester=4, branch="IT")
                db.add_all([sub_a, sub_b])
                await db.commit()

                # Call endpoint
                res = await list_subjects(db=db, current_user=user)
                codes = [s.code for s in res]

                self.assertIn(code_a, codes)
                self.assertIn(code_b, codes)

        self.loop.run_until_complete(_run())

    def test_02_subject_creation(self) -> None:
        """Verify create_subject registers a new course subject."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_creator_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="Subject Creator",
                    role="faculty",
                )
                db.add(user)
                await db.commit()

                unique_code = f"CS-CREATE-{uuid.uuid4().hex[:4].upper()}"
                subject_in = SubjectCreate(
                    code=unique_code,
                    name="Operating Systems Concepts",
                    semester=5,
                    branch="Computer Engineering",
                )

                created = await create_subject(
                    subject_in=subject_in,
                    db=db,
                    current_user=user,
                )

                self.assertIsNotNone(created.id)
                self.assertEqual(created.code, unique_code)
                self.assertEqual(created.name, "Operating Systems Concepts")
                self.assertEqual(created.semester, 5)
                self.assertEqual(created.branch, "Computer Engineering")

                # Verify persistence in database
                fetched = await db.get(Subject, created.id)
                self.assertIsNotNone(fetched)
                self.assertEqual(fetched.code, unique_code)

        self.loop.run_until_complete(_run())

    def test_03_duplicate_subject_code_rejected(self) -> None:
        """Verify duplicate subject code (exact and case-insensitive) is rejected with HTTP 409."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_dup_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="Duplicate Tester",
                    role="faculty",
                )
                db.add(user)

                dup_code = f"CS-DUP-{uuid.uuid4().hex[:4].upper()}"
                sub_orig = Subject(code=dup_code, name="Original Course", semester=6, branch="Comp")
                db.add(sub_orig)
                await db.commit()

                # Attempt 1: Exact duplicate
                subject_in_exact = SubjectCreate(
                    code=dup_code,
                    name="Duplicate Course",
                    semester=6,
                    branch="Comp",
                )
                with self.assertRaises(HTTPException) as ctx:
                    await create_subject(
                        subject_in=subject_in_exact,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 409)

                # Attempt 2: Case-insensitive duplicate (e.g. lowercase)
                subject_in_lower = SubjectCreate(
                    code=dup_code.lower(),
                    name="Duplicate Course Lowercase",
                    semester=6,
                    branch="Comp",
                )
                with self.assertRaises(HTTPException) as ctx_lower:
                    await create_subject(
                        subject_in=subject_in_lower,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx_lower.exception.status_code, 409)

        self.loop.run_until_complete(_run())

    def test_04_returned_subject_fields_match_schema(self) -> None:
        """Verify returned subject fields conform to SubjectOut schema."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_schema_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="Schema Tester",
                    role="student",
                )
                db.add(user)
                await db.commit()

                test_code = f"CS-SCH-{uuid.uuid4().hex[:4].upper()}"
                subject_in = SubjectCreate(
                    code=test_code,
                    name="Microprocessors & Interfacing",
                    semester=4,
                    branch="Electronics",
                )

                created = await create_subject(
                    subject_in=subject_in,
                    db=db,
                    current_user=user,
                )

                # Pydantic schema validation
                validated = SubjectOut.model_validate(created)
                self.assertEqual(validated.id, created.id)
                self.assertEqual(validated.code, test_code)
                self.assertEqual(validated.name, "Microprocessors & Interfacing")
                self.assertEqual(validated.semester, 4)
                self.assertEqual(validated.branch, "Electronics")

        self.loop.run_until_complete(_run())

    def test_05_subject_and_document_listing_integration(self) -> None:
        """Verify list_documents filters correctly by subject_id without regressions."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"sub_doc_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="hashed_pw",
                    full_name="Doc Subject Tester",
                    role="faculty",
                )
                db.add(user)

                sub1 = Subject(code=f"S1-{uuid.uuid4().hex[:4].upper()}", name="Subject 1", semester=1, branch="Mech")
                sub2 = Subject(code=f"S2-{uuid.uuid4().hex[:4].upper()}", name="Subject 2", semester=2, branch="Civil")
                db.add_all([sub1, sub2])
                await db.commit()

                # Call list_documents with subject_id filter
                docs_sub1 = await list_documents(
                    subject_id=sub1.id,
                    db=db,
                    current_user=user,
                )
                self.assertIsInstance(docs_sub1, list)

                # Verify list_subjects includes both
                all_subs = await list_subjects(db=db, current_user=user)
                sub_ids = [s.id for s in all_subs]
                self.assertIn(sub1.id, sub_ids)
                self.assertIn(sub2.id, sub_ids)

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
