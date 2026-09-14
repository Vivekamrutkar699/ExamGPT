"""add pyq topic resolution audit

Revision ID: d2b5f7c0e4a1
Revises: c1a4e6b9d2f3
"""
from alembic import op
import sqlalchemy as sa

revision = "d2b5f7c0e4a1"
down_revision = "c1a4e6b9d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pyq_paper") as batch:
        batch.create_unique_constraint("uq_pyq_paper_subject_hash", ["subject_id", "content_hash"])
    with op.batch_alter_table("canonical_topic") as batch:
        batch.add_column(sa.Column("compatibility_question_id", sa.UUID(), nullable=True))
        batch.create_unique_constraint("uq_canonical_topic_compatibility_question", ["compatibility_question_id"])
        batch.create_foreign_key(
            "fk_canonical_topic_compatibility_question", "question", ["compatibility_question_id"], ["id"], ondelete="SET NULL"
        )
    op.create_table(
        "topic_resolution",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("best_topic_id", sa.UUID(), nullable=True),
        sa.Column("second_topic_id", sa.UUID(), nullable=True),
        sa.Column("best_similarity_score", sa.Float(), nullable=True),
        sa.Column("second_similarity_score", sa.Float(), nullable=True),
        sa.Column("similarity_threshold", sa.Float(), nullable=True),
        sa.Column("ambiguity_margin", sa.Float(), nullable=True),
        sa.Column("matcher_version", sa.String(length=100), nullable=False),
        sa.Column("resolution_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["variant_id"], ["question_variant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["best_topic_id"], ["canonical_topic.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["second_topic_id"], ["canonical_topic.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_topic_resolution_variant_id"), "topic_resolution", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_topic_resolution_variant_id"), table_name="topic_resolution")
    op.drop_table("topic_resolution")
    with op.batch_alter_table("canonical_topic") as batch:
        batch.drop_constraint("fk_canonical_topic_compatibility_question", type_="foreignkey")
        batch.drop_constraint("uq_canonical_topic_compatibility_question", type_="unique")
        batch.drop_column("compatibility_question_id")
    with op.batch_alter_table("pyq_paper") as batch:
        batch.drop_constraint("uq_pyq_paper_subject_hash", type_="unique")
