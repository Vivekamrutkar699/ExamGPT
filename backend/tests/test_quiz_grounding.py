import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.pyq_topic import (
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
)
from app.models.question import Question
from app.models.quiz import Quiz
from app.models.subject import Subject
from app.models.user import User
from app.repositories.quiz import quiz_repository
from app.schemas.quiz import QuizSubmission
from app.schemas.recommendation import RecommendationAction, TopicActionResponse
from app.api.v1.endpoints.analytics import execute_topic_recommendation_action
from app.services.quiz import quiz_service


class QuizGroundingAndIsolationTests(unittest.IsolatedAsyncioTestCase):
    """
    Tests proving subject grounding, subject isolation, topic/unit filtering,
    variation, malformed JSON handling, and recommendation action compatibility.
    """

    async def asyncSetUp(self):
        async with SessionLocal() as db:
            self.user = User(
                email=f"tester_{uuid.uuid4().hex[:6]}@sppu.edu.in",
                hashed_password="hashed_password",
                full_name="Grounding Tester",
                role="admin",
            )
            self.subject_dsa = Subject(
                code=f"DSA-{uuid.uuid4().hex[:4].upper()}",
                name="Data Structures and Algorithms",
                semester=3,
                branch="Computer Engineering",
            )
            self.subject_dbms = Subject(
                code=f"DBMS-{uuid.uuid4().hex[:4].upper()}",
                name="Database Management Systems",
                semester=4,
                branch="Information Technology",
            )
            db.add_all([self.user, self.subject_dsa, self.subject_dbms])
            await db.commit()
            await db.refresh(self.user)
            await db.refresh(self.subject_dsa)
            await db.refresh(self.subject_dbms)

            # Create document and chunks for DSA
            self.doc_dsa = Document(
                subject_id=self.subject_dsa.id,
                name="dsa_graphs_trees.pdf",
                storage_path="mock_uploads/dsa_graphs_trees.pdf",
                file_type="pdf",
                category="notes",
                processing_status="completed",
                uploaded_by=self.user.id,
            )
            # Create document and chunks for DBMS
            self.doc_dbms = Document(
                subject_id=self.subject_dbms.id,
                name="dbms_sql_normalization.pdf",
                storage_path="mock_uploads/dbms_sql_normalization.pdf",
                file_type="pdf",
                category="notes",
                processing_status="completed",
                uploaded_by=self.user.id,
            )
            db.add_all([self.doc_dsa, self.doc_dbms])
            await db.commit()
            await db.refresh(self.doc_dsa)
            await db.refresh(self.doc_dbms)

            # DSA chunks
            self.chunk_dsa_1 = Chunk(
                document_id=self.doc_dsa.id,
                chunk_index=0,
                content="Graphs consist of vertices and edges. Breadth-First Search (BFS) traverses level by level using a queue data structure.",
                unit_tag="Unit 3",
                metadata_json={"page": 1},
            )
            self.chunk_dsa_2 = Chunk(
                document_id=self.doc_dsa.id,
                chunk_index=1,
                content="Depth-First Search (DFS) traverses deep along each branch using a recursive call stack or explicit stack.",
                unit_tag="Unit 3",
                metadata_json={"page": 2},
            )
            self.chunk_dsa_unit1 = Chunk(
                document_id=self.doc_dsa.id,
                chunk_index=2,
                content="Asymptotic notations include Big-O for upper bound and Omega for lower bound time complexity analysis.",
                unit_tag="Unit 1",
                metadata_json={"page": 5},
            )

            # DBMS chunks
            self.chunk_dbms_1 = Chunk(
                document_id=self.doc_dbms.id,
                chunk_index=0,
                content="Relational Database Management Systems store structured data in relations or tables with primary keys.",
                unit_tag="Unit 2",
                metadata_json={"page": 10},
            )
            self.chunk_dbms_2 = Chunk(
                document_id=self.doc_dbms.id,
                chunk_index=1,
                content="Third Normal Form (3NF) eliminates transitive dependency between non-prime attributes and primary keys.",
                unit_tag="Unit 4",
                metadata_json={"page": 20},
            )

            db.add_all([
                self.chunk_dsa_1,
                self.chunk_dsa_2,
                self.chunk_dsa_unit1,
                self.chunk_dbms_1,
                self.chunk_dbms_2,
            ])
            await db.commit()

    async def asyncTearDown(self):
        async with SessionLocal() as db:
            # Clean up chunks, documents, quizzes, subjects, user
            quizzes_res = await db.execute(
                select(Quiz).where(
                    Quiz.subject_id.in_([self.subject_dsa.id, self.subject_dbms.id])
                )
            )
            for qz in quizzes_res.scalars().all():
                await db.delete(qz)

            chunks_res = await db.execute(
                select(Chunk).where(
                    Chunk.document_id.in_([self.doc_dsa.id, self.doc_dbms.id])
                )
            )
            for ch in chunks_res.scalars().all():
                await db.delete(ch)

            doc_res = await db.execute(
                select(Document).where(
                    Document.id.in_([self.doc_dsa.id, self.doc_dbms.id])
                )
            )
            for doc in doc_res.scalars().all():
                await db.delete(doc)

            subj_res = await db.execute(
                select(Subject).where(
                    Subject.id.in_([self.subject_dsa.id, self.subject_dbms.id])
                )
            )
            for sub in subj_res.scalars().all():
                await db.delete(sub)

            usr = await db.get(User, self.user.id)
            if usr:
                await db.delete(usr)
            await db.commit()

    async def test_a_and_b_subject_grounding_and_isolation(self):
        """
        Tests A & B:
        - DSA quiz retrieves DSA/Graph chunks and passes them to Ollama.
        - DBMS quiz retrieves DBMS chunks and passes them to Ollama.
        - Cross-subject leakage is strictly prevented.
        """
        captured_prompts = []

        async def fake_llm_create(*args, **kwargs):
            messages = kwargs.get("messages", [])
            user_msg = messages[-1]["content"] if messages else ""
            captured_prompts.append(user_msg)

            if "Data Structures" in user_msg or "BFS" in user_msg or "Graphs" in user_msg:
                content = json.dumps({
                    "questions": [
                        {
                            "id": "mcq_1",
                            "question": "Which data structure is used by Breadth-First Search (BFS)?",
                            "choices": {"A": "Queue", "B": "Stack", "C": "Priority Queue", "D": "Tree"},
                            "correct_answer": "A",
                            "explanation": "BFS uses a FIFO queue to traverse graph nodes level by level.",
                        },
                        {
                            "id": "mcq_2",
                            "question": "What elements constitute a graph?",
                            "choices": {"A": "Vertices and Edges", "B": "Tables and Rows", "C": "Primary keys", "D": "Tokens"},
                            "correct_answer": "A",
                            "explanation": "A graph is defined as a pair G = (V, E) of vertices and edges.",
                        },
                        {
                            "id": "mcq_3",
                            "question": "Depth-First Search (DFS) typically utilizes which mechanism?",
                            "choices": {"A": "Queue", "B": "Stack or recursion", "C": "Hash table", "D": "B-Tree"},
                            "correct_answer": "B",
                            "explanation": "DFS explores deeply using a recursion stack.",
                        },
                    ]
                })
            else:
                content = json.dumps({
                    "questions": [
                        {
                            "id": "mcq_1",
                            "question": "What does Third Normal Form (3NF) eliminate?",
                            "choices": {"A": "Transitive dependency", "B": "Primary keys", "C": "Partial dependency", "D": "Indexes"},
                            "correct_answer": "A",
                            "explanation": "3NF removes transitive dependencies where non-prime attributes depend on other non-prime attributes.",
                        },
                        {
                            "id": "mcq_2",
                            "question": "How do Relational Database Management Systems store structured data?",
                            "choices": {"A": "Relations or tables", "B": "Graph edges", "C": "Call stacks", "D": "Binary heaps"},
                            "correct_answer": "A",
                            "explanation": "RDBMS organizes structured data in relations or tables.",
                        },
                        {
                            "id": "mcq_3",
                            "question": "What uniquely identifies rows in an RDBMS relation?",
                            "choices": {"A": "Primary key", "B": "Foreign key", "C": "Index", "D": "Graph vertex"},
                            "correct_answer": "A",
                            "explanation": "Primary keys uniquely identify rows in database relations.",
                        },
                    ]
                })

            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = content
            resp.choices = [choice]
            return resp

        async with SessionLocal() as db:
            with patch("app.services.quiz.openai_client.chat.completions.create", side_effect=fake_llm_create):
                # 1. Generate DSA Quiz
                dsa_quiz = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dsa.id,
                    title="DSA Standard Quiz",
                    quiz_type="MCQ",
                )
                # 2. Generate DBMS Quiz
                dbms_quiz = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dbms.id,
                    title="DBMS Standard Quiz",
                    quiz_type="MCQ",
                )

        # Verify DSA prompt grounding and isolation
        dsa_prompt = captured_prompts[0]
        self.assertIn("Graphs consist of vertices and edges", dsa_prompt)
        self.assertIn("Breadth-First Search", dsa_prompt)
        self.assertNotIn("Relational Database Management Systems", dsa_prompt)
        self.assertNotIn("Third Normal Form", dsa_prompt)

        # Verify DBMS prompt grounding and isolation
        dbms_prompt = captured_prompts[1]
        self.assertIn("Relational Database Management Systems", dbms_prompt)
        self.assertIn("Third Normal Form", dbms_prompt)
        self.assertNotIn("Graphs consist of vertices and edges", dbms_prompt)
        self.assertNotIn("Breadth-First Search", dbms_prompt)

        # Verify DSA quiz questions
        dsa_qs = dsa_quiz.questions_data["questions"]
        self.assertEqual(len(dsa_qs), 3)
        self.assertIn("BFS", dsa_qs[0]["question"])
        self.assertEqual(dsa_qs[0]["correct_answer"], "A")
        # Ensure static linker/loader questions were NOT used
        for q in dsa_qs:
            self.assertNotIn("linker", q["question"].lower())
            self.assertNotIn("loader", q["question"].lower())

        # Verify DBMS quiz questions
        dbms_qs = dbms_quiz.questions_data["questions"]
        self.assertEqual(len(dbms_qs), 3)
        self.assertIn("Third Normal Form", dbms_qs[0]["question"])
        for q in dbms_qs:
            self.assertNotIn("linker", q["question"].lower())
            self.assertNotIn("loader", q["question"].lower())

    async def test_c_topic_aware_phase7d_preservation(self):
        """
        Test C: When topic_id is supplied and topic-linked Question records exist,
        Phase 7D canonical topic question behavior is preserved.
        """
        async with SessionLocal() as db:
            topic = CanonicalTopic(
                subject_id=self.subject_dsa.id,
                canonical_label="Binary Search Tree Traversal",
                normalized_label="binary search tree traversal",
                unit_tag="Unit 2",
            )
            db.add(topic)
            await db.flush()

            q = Question(
                subject_id=self.subject_dsa.id,
                text="Explain Inorder, Preorder, and Postorder traversal of Binary Trees.",
                marks_weight=10,
                unit_tag="Unit 2",
            )
            db.add(q)
            await db.flush()

            v = QuestionVariant(
                subject_id=self.subject_dsa.id,
                topic_id=topic.id,
                legacy_question_id=q.id,
                text=q.text,
                normalized_text="explain inorder preorder postorder traversal binary trees",
                normalized_hash=uuid.uuid4().hex,
                resolution_type="exact_match",
            )
            db.add(v)
            await db.commit()

            # Generate quiz with topic_id
            topic_quiz = await quiz_service.generate_quiz(
                db=db,
                subject_id=self.subject_dsa.id,
                title="BST Traversal Topic Quiz",
                quiz_type="MCQ",
                topic_id=topic.id,
                unit_tag="Unit 2",
            )

            qs = topic_quiz.questions_data["questions"]
            self.assertGreaterEqual(len(qs), 1)
            self.assertIn("Binary Trees", qs[0]["question"])
            self.assertIn(str(q.id), qs[0]["id"])
            self.assertIn("Grounded in verified topic question", qs[0]["explanation"])

    async def test_d_unit_filtering(self):
        """
        Test D: Unit filtering restricts chunk retrieval to the requested unit_tag.
        """
        captured_prompts = []

        async def fake_llm_create(*args, **kwargs):
            messages = kwargs.get("messages", [])
            captured_prompts.append(messages[-1]["content"])
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = json.dumps({
                "questions": [
                    {
                        "id": "mcq_1",
                        "question": "What is Big-O notation used for?",
                        "choices": {"A": "Upper bound complexity", "B": "Lower bound", "C": "Average bound", "D": "Exact bound"},
                        "correct_answer": "A",
                        "explanation": "Big-O characterizes upper asymptotic bounds.",
                    },
                    {
                        "id": "mcq_2",
                        "question": "What does Omega notation represent?",
                        "choices": {"A": "Lower bound complexity", "B": "Upper bound", "C": "Average case", "D": "Worst case"},
                        "correct_answer": "A",
                        "explanation": "Omega characterizes lower asymptotic bounds.",
                    },
                    {
                        "id": "mcq_3",
                        "question": "What is asymptotic complexity analysis?",
                        "choices": {"A": "Analyzing resource growth", "B": "Counting bits", "C": "Compiling source", "D": "Executing loaders"},
                        "correct_answer": "A",
                        "explanation": "Asymptotic analysis observes scaling behavior.",
                    },
                ]
            })
            resp.choices = [choice]
            return resp

        async with SessionLocal() as db:
            with patch("app.services.quiz.openai_client.chat.completions.create", side_effect=fake_llm_create):
                unit_quiz = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dsa.id,
                    title="DSA Unit 1 Quiz",
                    quiz_type="MCQ",
                    unit_tag="Unit 1",
                )

        prompt = captured_prompts[0]
        self.assertIn("Asymptotic notations", prompt)
        self.assertIn("Big-O", prompt)
        # Unit 3 chunks should not be present when Unit 1 is strictly filtered
        self.assertNotIn("Breadth-First Search", prompt)

    async def test_e_and_f_quiz_variation(self):
        """
        Test E & F: Standard quiz generation with different LLM completions
        produces distinct question sets (demonstrating variation capability).
        """
        call_count = 0

        async def varied_llm_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                content = json.dumps({
                    "questions": [
                        {
                            "id": "mcq_1",
                            "question": "First generation: Which data structure does BFS use?",
                            "choices": {"A": "Queue", "B": "Stack", "C": "Tree", "D": "Heap"},
                            "correct_answer": "A",
                            "explanation": "BFS uses queue.",
                        },
                        {
                            "id": "mcq_2",
                            "question": "First generation: Graph representation method?",
                            "choices": {"A": "Adjacency matrix", "B": "Stack", "C": "Token", "D": "Pointer"},
                            "correct_answer": "A",
                            "explanation": "Matrix representation.",
                        },
                        {
                            "id": "mcq_3",
                            "question": "First generation: Vertex count in graph?",
                            "choices": {"A": "Order", "B": "Size", "C": "Rank", "D": "Height"},
                            "correct_answer": "A",
                            "explanation": "Order of graph.",
                        },
                    ]
                })
            else:
                content = json.dumps({
                    "questions": [
                        {
                            "id": "mcq_1",
                            "question": "Second generation: Which traversal uses recursion stack?",
                            "choices": {"A": "DFS", "B": "BFS", "C": "Kruskal", "D": "Prim"},
                            "correct_answer": "A",
                            "explanation": "DFS uses stack.",
                        },
                        {
                            "id": "mcq_2",
                            "question": "Second generation: Cycle detection in directed graphs?",
                            "choices": {"A": "Back edge in DFS", "B": "Queue empty", "C": "Leaf node", "D": "Binary tree"},
                            "correct_answer": "A",
                            "explanation": "Back edges indicate cycles.",
                        },
                        {
                            "id": "mcq_3",
                            "question": "Second generation: Connected components discovery?",
                            "choices": {"A": "Traversal algorithm", "B": "Lexer", "C": "Linker", "D": "Loader"},
                            "correct_answer": "A",
                            "explanation": "Connected components can be found via traversal.",
                        },
                    ]
                })

            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = content
            resp.choices = [choice]
            return resp

        async with SessionLocal() as db:
            with patch("app.services.quiz.openai_client.chat.completions.create", side_effect=varied_llm_create):
                quiz1 = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dsa.id,
                    title="Variation Quiz 1",
                    quiz_type="MCQ",
                )
                quiz2 = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dsa.id,
                    title="Variation Quiz 2",
                    quiz_type="MCQ",
                )

        q1_texts = [q["question"] for q in quiz1.questions_data["questions"]]
        q2_texts = [q["question"] for q in quiz2.questions_data["questions"]]

        self.assertNotEqual(q1_texts, q2_texts)
        self.assertIn("First generation", q1_texts[0])
        self.assertIn("Second generation", q2_texts[0])

    async def test_g_malformed_llm_output_rejected(self):
        """
        Test G: Invalid/malformed JSON returned from the LLM is rejected
        safely with HTTP 502 Bad Gateway and does not save a broken quiz.
        """
        async def malformed_llm_create(*args, **kwargs):
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = "Sorry, I am unable to generate questions from this context right now."
            resp.choices = [choice]
            return resp

        async with SessionLocal() as db:
            with patch("app.services.quiz.openai_client.chat.completions.create", side_effect=malformed_llm_create):
                with self.assertRaises(HTTPException) as ctx:
                    await quiz_service.generate_quiz(
                        db=db,
                        subject_id=self.subject_dsa.id,
                        title="Malformed Quiz Test",
                        quiz_type="MCQ",
                    )
                self.assertEqual(ctx.exception.status_code, 502)

    async def test_h_insufficient_study_material_returns_400(self):
        """
        Test H: A subject with zero study material chunks returns HTTP 400 Bad Request
        and does NOT silently fall back to static mock linker/loader questions.
        """
        async with SessionLocal() as db:
            empty_subject = Subject(
                code=f"EMPTY-{uuid.uuid4().hex[:4].upper()}",
                name="Empty Notes Subject",
                semester=5,
                branch="Mechanical Engineering",
            )
            db.add(empty_subject)
            await db.commit()
            await db.refresh(empty_subject)

            with self.assertRaises(HTTPException) as ctx:
                await quiz_service.generate_quiz(
                    db=db,
                    subject_id=empty_subject.id,
                    title="Empty Subject Quiz",
                    quiz_type="MCQ",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Insufficient study material found", ctx.exception.detail)

            # Cleanup empty_subject
            await db.delete(empty_subject)
            await db.commit()

    async def test_i_quiz_submission_and_evaluation_flow(self):
        """
        Test I: Grounded generated quiz can be submitted and graded accurately.
        """
        async def fake_llm_create(*args, **kwargs):
            resp = MagicMock()
            choice = MagicMock()
            choice.message.content = json.dumps({
                "questions": [
                    {
                        "id": "mcq_1",
                        "question": "What is BFS time complexity on adjacency list?",
                        "choices": {"A": "O(V + E)", "B": "O(V^2)", "C": "O(1)", "D": "O(log V)"},
                        "correct_answer": "A",
                        "explanation": "BFS visits all vertices and explores all edges.",
                    },
                    {
                        "id": "mcq_2",
                        "question": "Which queue property does BFS rely on?",
                        "choices": {"A": "FIFO", "B": "LIFO", "C": "Random", "D": "None"},
                        "correct_answer": "A",
                        "explanation": "FIFO ensures level-order traversal.",
                    },
                    {
                        "id": "mcq_3",
                        "question": "Which graph traversal discovers shortest path in unweighted graphs?",
                        "choices": {"A": "BFS", "B": "DFS", "C": "Topological sort", "D": "Binary search"},
                        "correct_answer": "A",
                        "explanation": "BFS guarantees shortest path in unweighted graphs.",
                    },
                ]
            })
            resp.choices = [choice]
            return resp

        async with SessionLocal() as db:
            with patch("app.services.quiz.openai_client.chat.completions.create", side_effect=fake_llm_create):
                quiz = await quiz_service.generate_quiz(
                    db=db,
                    subject_id=self.subject_dsa.id,
                    title="Submission Test Quiz",
                    quiz_type="MCQ",
                )

            # Submit 2 correct, 1 incorrect
            submission = QuizSubmission(
                answers={
                    "mcq_1": "A",  # Correct
                    "mcq_2": "A",  # Correct
                    "mcq_3": "B",  # Incorrect (correct is A)
                }
            )

            grade = await quiz_service.grade_quiz(db, quiz_id=quiz.id, submission=submission)
            self.assertEqual(grade.total_questions, 3)
            self.assertEqual(grade.correct_answers, 2)
            self.assertEqual(grade.score_percent, 66.7)
            self.assertTrue(grade.feedback[0]["is_correct"])
            self.assertTrue(grade.feedback[1]["is_correct"])
    async def test_j_recommendation_quiz_and_assess_actions_compatibility(self):
        """
        Test J: Recommendation actions QUIZ and ASSESS invoke quiz generation seamlessly,
        preserving sanitized questions and valid submission endpoints.
        """
        async with SessionLocal() as db:
            topic = CanonicalTopic(
                subject_id=self.subject_dsa.id,
                canonical_label="Shortest Path Dijkstra Algorithm",
                normalized_label="shortest path dijkstra algorithm",
                unit_tag="Unit 3",
            )
            db.add(topic)
            await db.flush()

            paper = PYQPaper(
                subject_id=self.subject_dsa.id,
                title="May 2024 Exam",
                exam_session="MAY_JUN",
                exam_year=2024,
            )
            db.add(paper)
            await db.flush()

            q = Question(
                subject_id=self.subject_dsa.id,
                text="Explain Dijkstra's Single Source Shortest Path Algorithm.",
                marks_weight=10,
                unit_tag="Unit 3",
            )
            db.add(q)
            await db.flush()

            v = QuestionVariant(
                subject_id=self.subject_dsa.id,
                topic_id=topic.id,
                legacy_question_id=q.id,
                text=q.text,
                normalized_text="explain dijkstras single source shortest path algorithm",
                normalized_hash=uuid.uuid4().hex,
                resolution_type="exact_match",
            )
            db.add(v)
            await db.flush()

            occ = PYQQuestionOccurrence(
                paper_id=paper.id,
                variant_id=v.id,
                question_number="Q4a",
                source_text=q.text,
                marks_weight=10,
            )
            db.add(occ)
            await db.commit()

            # Execute ASSESS action (no student data yet)
            res = await execute_topic_recommendation_action(
                subject_id=self.subject_dsa.id,
                topic_id=topic.id,
                db=db,
                current_user=self.user,
            )

            self.assertIsInstance(res, TopicActionResponse)
            self.assertEqual(res.action, RecommendationAction.ASSESS)
            self.assertIsNotNone(res.quiz_data)
            self.assertEqual(res.quiz_data.quiz_type, "MCQ")
            self.assertIn("submit", res.quiz_data.submission_endpoint)
            self.assertGreaterEqual(res.quiz_data.total_questions, 1)
            # Ensure answer keys were sanitized from questions payload
            for q_item in res.quiz_data.questions:
                self.assertNotIn("correct_answer", q_item)
                self.assertNotIn("explanation", q_item)


if __name__ == "__main__":
    unittest.main()

