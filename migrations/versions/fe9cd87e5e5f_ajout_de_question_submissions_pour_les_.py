"""ajout de question_submissions pour les suggestions de joueurs

Revision ID: fe9cd87e5e5f
Revises: 5489101f9e0f
Create Date: 2026-09-08 14:35:10.275261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe9cd87e5e5f'
down_revision = '5489101f9e0f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "question_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.JSON(), nullable=False),
        sa.Column("content_type", sa.String(length=10), nullable=False, server_default="film"),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="moyen"),
        sa.Column("was_edited_by_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_prompt", sa.Text(), nullable=True),
        sa.Column("reviewed_payload", sa.JSON(), nullable=True),
        sa.Column("reviewed_correct_answer", sa.JSON(), nullable=True),
        sa.Column("reviewed_content_type", sa.String(length=10), nullable=True),
        sa.Column("reviewed_difficulty", sa.String(length=20), nullable=True),
        sa.Column("rejection_reason", sa.String(length=200), nullable=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "submission_tags",
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("question_submissions.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )

    op.create_table(
        "submission_reviewed_tags",
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("question_submissions.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("submission_reviewed_tags")
    op.drop_table("submission_tags")
    op.drop_table("question_submissions")
