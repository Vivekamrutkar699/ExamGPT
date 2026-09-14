"""add_pyq_topic_intelligence_tables

Revision ID: c1a4e6b9d2f3
Revises: bad5fa543ee1
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a4e6b9d2f3"
down_revision: Union[str, Sequence[str], None] = "bad5fa543ee1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add topic-intelligence tables without changing legacy PYQ data."""
    op.create_table(
        "pyq_paper",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("exam_year", sa.Integer(), nullable=True),
        sa.Column("exam_session", sa.String(length=100), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pyq_paper_subject_id"), "pyq_paper", ["subject_id"], unique=False)

    op.create_table(
        "canonical_topic",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("canonical_label", sa.String(length=255), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=False),
        sa.Column("label_source", sa.String(length=50), nullable=False),
        sa.Column("is_label_reviewed", sa.Boolean(), nullable=False),
        sa.Column("unit_tag", sa.String(length=100), nullable=True),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model_version", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_canonical_topic_subject_id"),
        "canonical_topic",
        ["subject_id"],
        unique=False,
    )

    op.create_table(
        "question_variant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("legacy_question_id", sa.UUID(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model_version", sa.String(length=100), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("matcher_version", sa.String(length=100), nullable=True),
        sa.Column("resolution_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["legacy_question_id"], ["question.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["canonical_topic.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_question_id"),
        sa.UniqueConstraint("subject_id", "normalized_hash", name="uq_question_variant_subject_hash"),
    )
    op.create_index(
        op.f("ix_question_variant_subject_id"),
        "question_variant",
        ["subject_id"],
        unique=False,
    )
    op.create_index("ix_question_variant_topic_id", "question_variant", ["topic_id"], unique=False)

    op.create_table(
        "pyq_question_occurrence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("question_number", sa.String(length=50), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("marks_weight", sa.Integer(), nullable=False),
        sa.Column("unit_tag", sa.String(length=100), nullable=True),
        sa.Column("chapter", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["pyq_paper.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["question_variant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pyq_question_occurrence_paper_id"),
        "pyq_question_occurrence",
        ["paper_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyq_question_occurrence_variant_id"),
        "pyq_question_occurrence",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_pyq_question_occurrence_paper_variant",
        "pyq_question_occurrence",
        ["paper_id", "variant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only Phase 1 tables; legacy tables and rows remain untouched."""
    op.drop_index("ix_pyq_question_occurrence_paper_variant", table_name="pyq_question_occurrence")
    op.drop_index(op.f("ix_pyq_question_occurrence_variant_id"), table_name="pyq_question_occurrence")
    op.drop_index(op.f("ix_pyq_question_occurrence_paper_id"), table_name="pyq_question_occurrence")
    op.drop_table("pyq_question_occurrence")
    op.drop_index("ix_question_variant_topic_id", table_name="question_variant")
    op.drop_index(op.f("ix_question_variant_subject_id"), table_name="question_variant")
    op.drop_table("question_variant")
    op.drop_index(op.f("ix_canonical_topic_subject_id"), table_name="canonical_topic")
    op.drop_table("canonical_topic")
    op.drop_index(op.f("ix_pyq_paper_subject_id"), table_name="pyq_paper")
    op.drop_table("pyq_paper")
