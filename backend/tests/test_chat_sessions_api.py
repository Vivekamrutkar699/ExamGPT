import asyncio
import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from app.database.session import SessionLocal
from app.models.chat import ChatSession
from app.models.subject import Subject
from app.models.user import User
from unittest.mock import patch, AsyncMock
from app.schemas.chat import (
    ChatSessionCreate, 
    ChatSessionOut, 
    ChatQueryRequest, 
    ChatHistoryItem, 
    ChatQueryResponse
)
from app.api.v1.endpoints.chats import (
    create_chat_session, 
    list_chat_sessions_by_subject,
    get_session_chat_history,
    query_chat_session
)
from app.repositories.chat import chat_repository
from app.main import app


class ChatSessionsApiTests(unittest.TestCase):
    """
    Focused tests for GET /api/v1/chats/sessions/subject/{subject_id}:
    1. Authenticated user retrieves sessions for a specific subject
    2. User isolation (Student A cannot see Student B's chat sessions)
    3. Subject isolation (Sessions from Subject B are not returned for Subject A)
    4. Non-existent subject returns 404 Not Found
    5. Empty state returns empty list
    6. Response conforms to ChatSessionOut schema
    """

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_01_list_sessions_for_subject_success(self) -> None:
        """Verify authenticated user receives their chat sessions for a specific subject."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"chat_student_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Chat Student",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-CHAT-{uuid.uuid4().hex[:4].upper()}",
                    name="Cloud Computing",
                    semester=7,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                # Create 2 sessions for this subject
                s1 = ChatSession(user_id=user.id, subject_id=subject.id, title="Session 1")
                s2 = ChatSession(user_id=user.id, subject_id=subject.id, title="Session 2")
                db.add_all([s1, s2])
                await db.commit()

                # Call endpoint
                sessions = await list_chat_sessions_by_subject(
                    subject_id=subject.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(len(sessions), 2)
                titles = [s.title for s in sessions]
                self.assertIn("Session 1", titles)
                self.assertIn("Session 2", titles)
                for s in sessions:
                    self.assertEqual(s.subject_id, subject.id)
                    self.assertEqual(s.user_id, user.id)
                    # Validate schema compatibility
                    out = ChatSessionOut.model_validate(s)
                    self.assertEqual(out.id, s.id)

        self.loop.run_until_complete(_run())

    def test_02_user_isolation(self) -> None:
        """Verify Student A cannot see Student B's chat sessions for the same subject."""
        async def _run():
            async with SessionLocal() as db:
                student_a = User(
                    email=f"alice_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Alice",
                    role="student",
                )
                student_b = User(
                    email=f"bob_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Bob",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-ISO-{uuid.uuid4().hex[:4].upper()}",
                    name="Operating Systems",
                    semester=5,
                    branch="Computer Engineering",
                )
                db.add_all([student_a, student_b, subject])
                await db.commit()
                await db.refresh(student_a)
                await db.refresh(student_b)
                await db.refresh(subject)

                # Alice's session
                s_alice = ChatSession(user_id=student_a.id, subject_id=subject.id, title="Alice Notes")
                # Bob's session
                s_bob = ChatSession(user_id=student_b.id, subject_id=subject.id, title="Bob Notes")
                db.add_all([s_alice, s_bob])
                await db.commit()

                # Alice queries
                alice_sessions = await list_chat_sessions_by_subject(
                    subject_id=subject.id,
                    db=db,
                    current_user=student_a,
                )
                self.assertEqual(len(alice_sessions), 1)
                self.assertEqual(alice_sessions[0].title, "Alice Notes")

                # Bob queries
                bob_sessions = await list_chat_sessions_by_subject(
                    subject_id=subject.id,
                    db=db,
                    current_user=student_b,
                )
                self.assertEqual(len(bob_sessions), 1)
                self.assertEqual(bob_sessions[0].title, "Bob Notes")

        self.loop.run_until_complete(_run())

    def test_03_subject_isolation(self) -> None:
        """Verify sessions from Subject B are not returned when querying Subject A."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"cross_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Cross Subject Student",
                    role="student",
                )
                sub_a = Subject(
                    code=f"CS-A-{uuid.uuid4().hex[:4].upper()}",
                    name="Subject Alpha",
                    semester=5,
                    branch="Computer",
                )
                sub_b = Subject(
                    code=f"CS-B-{uuid.uuid4().hex[:4].upper()}",
                    name="Subject Beta",
                    semester=5,
                    branch="Computer",
                )
                db.add_all([user, sub_a, sub_b])
                await db.commit()
                await db.refresh(user)
                await db.refresh(sub_a)
                await db.refresh(sub_b)

                s_a = ChatSession(user_id=user.id, subject_id=sub_a.id, title="Alpha Session")
                s_b = ChatSession(user_id=user.id, subject_id=sub_b.id, title="Beta Session")
                db.add_all([s_a, s_b])
                await db.commit()

                # Query Subject A
                res_a = await list_chat_sessions_by_subject(
                    subject_id=sub_a.id,
                    db=db,
                    current_user=user,
                )
                self.assertEqual(len(res_a), 1)
                self.assertEqual(res_a[0].title, "Alpha Session")

                # Query Subject B
                res_b = await list_chat_sessions_by_subject(
                    subject_id=sub_b.id,
                    db=db,
                    current_user=user,
                )
                self.assertEqual(len(res_b), 1)
                self.assertEqual(res_b[0].title, "Beta Session")

        self.loop.run_until_complete(_run())

    def test_04_non_existent_subject_returns_404(self) -> None:
        """Verify querying a non-existent subject raises a 404 HTTPException."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"nf_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="NotFound Student",
                    role="student",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                random_subject_id = uuid.uuid4()
                with self.assertRaises(HTTPException) as ctx:
                    await list_chat_sessions_by_subject(
                        subject_id=random_subject_id,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertIn("Course Subject ID does not exist", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_05_empty_sessions_for_valid_subject(self) -> None:
        """Verify empty list is returned when a valid subject has no sessions for the user."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"empty_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Empty Student",
                    role="student",
                )
                sub = Subject(
                    code=f"CS-EMPTY-{uuid.uuid4().hex[:4].upper()}",
                    name="Empty Course",
                    semester=3,
                    branch="Comp",
                )
                db.add_all([user, sub])
                await db.commit()
                await db.refresh(user)
                await db.refresh(sub)

                res = await list_chat_sessions_by_subject(
                    subject_id=sub.id,
                    db=db,
                    current_user=user,
                )
                self.assertEqual(res, [])

        self.loop.run_until_complete(_run())

    def test_06_create_chat_session_success_and_schema(self) -> None:
        """Verify authenticated session creation associates subject and ownership properly."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"create_sess_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Session Creator",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-NEW-{uuid.uuid4().hex[:4].upper()}",
                    name="Compiler Construction",
                    semester=6,
                    branch="Computer Engineering",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                # Call create_chat_session with payload
                payload = ChatSessionCreate(
                    subject_id=subject.id,
                    title="Review Loaders and Linkers",
                )
                created = await create_chat_session(
                    session_in=payload,
                    db=db,
                    current_user=user,
                )

                self.assertIsNotNone(created.id)
                self.assertEqual(created.user_id, user.id)
                self.assertEqual(created.subject_id, subject.id)
                self.assertEqual(created.title, "Review Loaders and Linkers")
                self.assertIsNotNone(created.created_at)

                # Validate response schema conformity
                out = ChatSessionOut.model_validate(created)
                self.assertEqual(out.id, created.id)
                self.assertEqual(out.user_id, user.id)
                self.assertEqual(out.subject_id, subject.id)
                self.assertEqual(out.title, "Review Loaders and Linkers")

        self.loop.run_until_complete(_run())

    def test_07_post_chat_sessions_route_registered(self) -> None:
        """Verify both POST /api/v1/chats/ and POST /api/v1/chats/sessions exist in FastAPI router."""
        openapi_paths = app.openapi()["paths"]
        self.assertIn("/api/v1/chats/", openapi_paths)
        self.assertIn("post", openapi_paths["/api/v1/chats/"])
        self.assertIn("/api/v1/chats/sessions", openapi_paths)
        self.assertIn("post", openapi_paths["/api/v1/chats/sessions"])

    def test_08_create_session_invalid_subject_returns_404(self) -> None:
        """Verify session creation with a non-existent subject raises 404 HTTPException."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"fail_user_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Fail User",
                    role="student",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                invalid_subject_id = uuid.uuid4()
                payload = ChatSessionCreate(
                    subject_id=invalid_subject_id,
                    title="Invalid Subject Chat",
                )
                with self.assertRaises(HTTPException) as ctx:
                    await create_chat_session(
                        session_in=payload,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 404)
                self.assertIn("Course Subject ID not found", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_09_create_session_preserves_user_isolation(self) -> None:
        """Verify session created by User A is not visible in User B's subject sessions."""
        async def _run():
            async with SessionLocal() as db:
                user_a = User(
                    email=f"iso_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Iso A",
                    role="student",
                )
                user_b = User(
                    email=f"iso_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Iso B",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-ISO2-{uuid.uuid4().hex[:4].upper()}",
                    name="Distributed Systems",
                    semester=8,
                    branch="Computer Engineering",
                )
                db.add_all([user_a, user_b, subject])
                await db.commit()
                await db.refresh(user_a)
                await db.refresh(user_b)
                await db.refresh(subject)

                # User A creates a session
                payload = ChatSessionCreate(
                    subject_id=subject.id,
                    title="User A Private Topic",
                )
                sess_a = await create_chat_session(
                    session_in=payload,
                    db=db,
                    current_user=user_a,
                )
                self.assertEqual(sess_a.user_id, user_a.id)

                # User B lists sessions for this subject
                user_b_sessions = await list_chat_sessions_by_subject(
                    subject_id=subject.id,
                    db=db,
                    current_user=user_b,
                )
                # User B should see 0 sessions
                self.assertEqual(len(user_b_sessions), 0)

                # User A lists sessions for this subject
                user_a_sessions = await list_chat_sessions_by_subject(
                    subject_id=subject.id,
                    db=db,
                    current_user=user_a,
                )
                self.assertEqual(len(user_a_sessions), 1)
                self.assertEqual(user_a_sessions[0].id, sess_a.id)

        self.loop.run_until_complete(_run())

    def test_10_history_retrieval_for_owned_session(self) -> None:
        """Verify authenticated user can retrieve turn history (query, response, citations)."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"hist_user_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="History Student",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-HIST-{uuid.uuid4().hex[:4].upper()}",
                    name="Systems Programming",
                    semester=5,
                    branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                session = ChatSession(user_id=user.id, subject_id=subject.id, title="Linker Prep")
                db.add(session)
                await db.commit()
                await db.refresh(session)

                # Add a user question and an assistant answer with citations
                await chat_repository.add_message(
                    db=db,
                    session_id=session.id,
                    role="user",
                    content="What is relocation in loaders?",
                )
                await chat_repository.add_message(
                    db=db,
                    session_id=session.id,
                    role="assistant",
                    content="Relocation is the process of adjusting program addresses...",
                    citations=[{"chunk_id": "c1", "content": "Relocation logic...", "page": 2, "category": "notes"}],
                )

                # Retrieve history via endpoint
                history = await get_session_chat_history(
                    session_id=session.id,
                    db=db,
                    current_user=user,
                )

                self.assertEqual(len(history), 1)
                item = history[0]
                self.assertEqual(item.query, "What is relocation in loaders?")
                self.assertIn("Relocation is the process", item.response)
                self.assertEqual(len(item.citations), 1)
                self.assertEqual(item.citations[0]["page"], 2)
                self.assertIsNotNone(item.created_at)

                # Schema verification
                out = ChatHistoryItem.model_validate(item)
                self.assertEqual(out.query, "What is relocation in loaders?")

        self.loop.run_until_complete(_run())

    def test_11_history_cannot_be_accessed_by_another_user(self) -> None:
        """Verify 403 Forbidden is raised when accessing another user's session history."""
        async def _run():
            async with SessionLocal() as db:
                user_a = User(
                    email=f"h_a_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="User A",
                    role="student",
                )
                user_b = User(
                    email=f"h_b_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="User B",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-HA-{uuid.uuid4().hex[:4].upper()}",
                    name="Security Systems",
                    semester=6,
                    branch="Comp",
                )
                db.add_all([user_a, user_b, subject])
                await db.commit()
                await db.refresh(user_a)
                await db.refresh(user_b)
                await db.refresh(subject)

                session_a = ChatSession(user_id=user_a.id, subject_id=subject.id, title="User A Chat")
                db.add(session_a)
                await db.commit()
                await db.refresh(session_a)

                with self.assertRaises(HTTPException) as ctx:
                    await get_session_chat_history(
                        session_id=session_a.id,
                        db=db,
                        current_user=user_b,
                    )
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("do not have access", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_12_nonexistent_session_returns_404_for_history_and_query(self) -> None:
        """Verify 404 is returned when session ID does not exist."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"h_nf_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="NF User",
                    role="student",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                random_sess_id = uuid.uuid4()
                # History check
                with self.assertRaises(HTTPException) as ctx_h:
                    await get_session_chat_history(
                        session_id=random_sess_id,
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx_h.exception.status_code, 404)

                # Query check
                with self.assertRaises(HTTPException) as ctx_q:
                    await query_chat_session(
                        session_id=random_sess_id,
                        query_in=ChatQueryRequest(query="test"),
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx_q.exception.status_code, 404)

        self.loop.run_until_complete(_run())

    def test_13_query_on_owned_session_reaches_chat_service(self) -> None:
        """Verify query on owned session executes and returns frontend-compatible response."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"q_owner_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Query Owner",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-Q1-{uuid.uuid4().hex[:4].upper()}",
                    name="Embedded Systems",
                    semester=6,
                    branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                session = ChatSession(user_id=user.id, subject_id=subject.id, title="Embedded Q&A")
                db.add(session)
                await db.commit()
                await db.refresh(session)

                mock_reply = {
                    "response": "Embedded interrupts preempt normal execution.",
                    "context_chunks": [
                        {"chunk_id": "chunk-101", "content": "Interrupt handling...", "metadata": {"page": 3}, "category": "notes"}
                    ],
                }

                with patch("app.services.agents.agent_orchestration_service.run_agent_workflow", new=AsyncMock(return_value=mock_reply)):
                    res = await query_chat_session(
                        session_id=session.id,
                        query_in=ChatQueryRequest(query="How do interrupts work?"),
                        db=db,
                        current_user=user,
                    )

                self.assertEqual(res.response, "Embedded interrupts preempt normal execution.")
                self.assertEqual(res.content, "Embedded interrupts preempt normal execution.")
                self.assertEqual(res.query, "How do interrupts work?")
                self.assertEqual(len(res.citations), 1)
                self.assertEqual(res.citations[0]["page"], 3)
                self.assertEqual(res.session_id, session.id)

                # Validate response schema
                out = ChatQueryResponse.model_validate(res)
                self.assertEqual(out.response, res.response)

                # Verify messages saved to database
                db_msgs = await chat_repository.get_messages_by_session(db, session_id=session.id)
                self.assertEqual(len(db_msgs), 2)
                self.assertEqual(db_msgs[0].role, "user")
                self.assertEqual(db_msgs[0].content, "How do interrupts work?")
                self.assertEqual(db_msgs[1].role, "assistant")
                self.assertEqual(db_msgs[1].content, "Embedded interrupts preempt normal execution.")

        self.loop.run_until_complete(_run())

    def test_14_query_cannot_be_performed_on_another_users_session(self) -> None:
        """Verify 403 Forbidden is raised when querying another user's chat session."""
        async def _run():
            async with SessionLocal() as db:
                user_a = User(
                    email=f"qa_owner_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Owner A",
                    role="student",
                )
                user_b = User(
                    email=f"qb_intruder_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Intruder B",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-QISO-{uuid.uuid4().hex[:4].upper()}",
                    name="Network Security",
                    semester=7,
                    branch="Comp",
                )
                db.add_all([user_a, user_b, subject])
                await db.commit()
                await db.refresh(user_a)
                await db.refresh(user_b)
                await db.refresh(subject)

                session_a = ChatSession(user_id=user_a.id, subject_id=subject.id, title="Private Sec Chat")
                db.add(session_a)
                await db.commit()
                await db.refresh(session_a)

                with self.assertRaises(HTTPException) as ctx:
                    await query_chat_session(
                        session_id=session_a.id,
                        query_in=ChatQueryRequest(query="Hacking into session?"),
                        db=db,
                        current_user=user_b,
                    )
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("do not have access", ctx.exception.detail)

        self.loop.run_until_complete(_run())

    def test_15_empty_query_rejected(self) -> None:
        """Verify 422 is raised when empty query is sent."""
        async def _run():
            async with SessionLocal() as db:
                user = User(
                    email=f"empty_q_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                    hashed_password="pw",
                    full_name="Empty Q",
                    role="student",
                )
                subject = Subject(
                    code=f"CS-EQ-{uuid.uuid4().hex[:4].upper()}",
                    name="Algorithms",
                    semester=4,
                    branch="Comp",
                )
                db.add_all([user, subject])
                await db.commit()
                await db.refresh(user)
                await db.refresh(subject)

                session = ChatSession(user_id=user.id, subject_id=subject.id, title="Algo Q")
                db.add(session)
                await db.commit()
                await db.refresh(session)

                with self.assertRaises(HTTPException) as ctx:
                    await query_chat_session(
                        session_id=session.id,
                        query_in=ChatQueryRequest(query="   "),
                        db=db,
                        current_user=user,
                    )
                self.assertEqual(ctx.exception.status_code, 422)

        self.loop.run_until_complete(_run())

    def test_16_history_and_query_routes_registered(self) -> None:
        """Verify GET .../history and POST .../query exist in OpenAPI paths."""
        openapi_paths = app.openapi()["paths"]
        self.assertIn("/api/v1/chats/sessions/{session_id}/history", openapi_paths)
        self.assertIn("get", openapi_paths["/api/v1/chats/sessions/{session_id}/history"])
        self.assertIn("/api/v1/chats/sessions/{session_id}/query", openapi_paths)
        self.assertIn("post", openapi_paths["/api/v1/chats/sessions/{session_id}/query"])


if __name__ == "__main__":
    unittest.main()
