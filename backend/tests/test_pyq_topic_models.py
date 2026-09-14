import os
import sqlite3
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
MIGRATION_REVISION = "c1a4e6b9d2f3"


class PYQTopicModelMetadataTests(unittest.TestCase):
    def test_topic_models_register_expected_tables_and_constraints(self) -> None:
        sys.path.insert(0, str(BACKEND_DIR))
        from app.database.base import Base

        expected_tables = {
            "pyq_paper",
            "canonical_topic",
            "question_variant",
            "pyq_question_occurrence",
        }
        self.assertTrue(expected_tables.issubset(Base.metadata.tables))

        variant = Base.metadata.tables["question_variant"]
        self.assertEqual(variant.c.topic_id.nullable, True)
        self.assertEqual(variant.c.resolution_type.nullable, False)
        self.assertEqual(variant.c.similarity_score.nullable, True)
        self.assertIn("uq_question_variant_subject_hash", {
            constraint.name for constraint in variant.constraints
        })


class PYQTopicMigrationTests(unittest.TestCase):
    def test_sqlite_upgrade_preserves_legacy_rows_and_adds_topic_tables(self) -> None:
        database_path = BACKEND_DIR / f".pyq_topic_migration_{uuid.uuid4().hex}.db"
        database_url = f"sqlite+aiosqlite:///./{database_path.name}"
        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url

        try:
            command = [sys.executable, "-m", "alembic", "-c", "alembic.ini"]
            subprocess.run(
                [*command, "upgrade", "bad5fa543ee1"],
                cwd=BACKEND_DIR,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            connection = sqlite3.connect(database_path)
            try:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute(
                    "INSERT INTO subject (id, code, name, semester, branch) VALUES (?, ?, ?, ?, ?)",
                    ("subject-1", "CS-TOPIC", "Topic Migration", 6, "Computer"),
                )
                connection.execute(
                    "INSERT INTO user (id, email, hashed_password, full_name, role, is_active, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "user-1",
                        "migration@example.test",
                        "hashed",
                        "Migration User",
                        "student",
                        1,
                        "2026-09-14 00:00:00",
                    ),
                )
                connection.execute(
                    "INSERT INTO question (id, subject_id, text, marks_weight, is_pyq, occurrences) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("question-1", "subject-1", "Legacy PYQ wording", 10, 1, 3),
                )
                connection.execute(
                    "INSERT INTO answers_evaluation "
                    "(id, user_id, question_id, user_submitted_answer, feedback, estimated_marks, "
                    "max_marks, evaluated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "evaluation-1",
                        "user-1",
                        "question-1",
                        "Legacy answer",
                        "Legacy feedback",
                        6.0,
                        10.0,
                        "2026-09-14 00:00:00",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            subprocess.run(
                [*command, "upgrade", "c1a4e6b9d2f3"],
                cwd=BACKEND_DIR,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            connection = sqlite3.connect(database_path)
            try:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertTrue({
                    "pyq_paper",
                    "canonical_topic",
                    "question_variant",
                    "pyq_question_occurrence",
                }.issubset(table_names))
                self.assertEqual(
                    connection.execute("SELECT occurrences FROM question WHERE id = ?", ("question-1",)).fetchone()[0],
                    3,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT max_marks FROM answers_evaluation WHERE id = ?", ("evaluation-1",)
                    ).fetchone()[0],
                    10.0,
                )

                variant_foreign_keys = {
                    row[2]: row[6]
                    for row in connection.execute("PRAGMA foreign_key_list(question_variant)")
                }
                self.assertEqual(variant_foreign_keys["canonical_topic"], "SET NULL")
                self.assertEqual(variant_foreign_keys["question"], "SET NULL")
                self.assertEqual(variant_foreign_keys["subject"], "CASCADE")

                occurrence_indexes = {
                    row[1]
                    for row in connection.execute("PRAGMA index_list(pyq_question_occurrence)")
                }
                self.assertIn("ix_pyq_question_occurrence_paper_variant", occurrence_indexes)
            finally:
                connection.close()
        finally:
            database_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
