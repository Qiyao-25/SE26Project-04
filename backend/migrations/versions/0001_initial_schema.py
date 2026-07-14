"""create initial PaperMate schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("authors", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("normalized_name", sa.String(255), nullable=False), sa.Column("display_name", sa.String(255), nullable=False), sa.Column("orcid", sa.String(64)), sa.UniqueConstraint("normalized_name"), sa.UniqueConstraint("orcid"))
    op.create_index("ix_authors_normalized_name", "authors", ["normalized_name"], unique=False)
    op.create_table("papers", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("arxiv_id", sa.String(128), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("abstract", sa.Text()), sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("primary_category", sa.String(128)), sa.Column("pdf_url", sa.Text()), sa.Column("source_url", sa.Text()), sa.Column("ingest_status", sa.String(32), nullable=False, server_default="metadata_only"), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.UniqueConstraint("arxiv_id"))
    op.create_index("ix_papers_arxiv_id", "papers", ["arxiv_id"], unique=False)
    op.create_index("ix_papers_primary_category", "papers", ["primary_category"], unique=False)
    op.create_table("paper_authors", sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), primary_key=True), sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id"), primary_key=True), sa.Column("author_order", sa.Integer(), nullable=False))
    op.create_table("paper_contents", sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), primary_key=True), sa.Column("storage_path", sa.Text(), nullable=False), sa.Column("checksum", sa.String(128), nullable=False), sa.Column("mime_type", sa.String(128), nullable=False), sa.Column("downloaded_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("checksum"))
    op.create_table("parse_tasks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False), sa.Column("task_type", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="queued"), sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error_code", sa.String(64)), sa.UniqueConstraint("idempotency_key"))
    op.create_index("ix_parse_tasks_paper_id", "parse_tasks", ["paper_id"], unique=False)
    op.create_table("structured_results", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False), sa.Column("parse_task_id", sa.Integer(), sa.ForeignKey("parse_tasks.id")), sa.Column("result_type", sa.String(64), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("content_json", sa.JSON(), nullable=False), sa.Column("source_locator", sa.JSON(), nullable=False), sa.Column("confidence", sa.Float()), sa.UniqueConstraint("paper_id", "result_type", "version", name="uq_result_version"))
    op.create_index("ix_structured_results_paper_id", "structured_results", ["paper_id"], unique=False)
    op.create_table("text_chunks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False), sa.Column("chunk_id", sa.String(128), nullable=False), sa.Column("page_no", sa.Integer()), sa.Column("section", sa.String(255)), sa.Column("content", sa.Text(), nullable=False), sa.Column("embedding", sa.JSON()), sa.UniqueConstraint("paper_id", "chunk_id", name="uq_chunk_per_paper"))
    op.create_index("ix_text_chunks_paper_id", "text_chunks", ["paper_id"], unique=False)
    op.create_index("ix_text_chunks_paper_page", "text_chunks", ["paper_id", "page_no"], unique=False)
    op.create_table("user_actions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.String(128), nullable=False), sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False), sa.Column("action_type", sa.String(64), nullable=False), sa.Column("payload_json", sa.JSON(), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_user_actions_paper_id", "user_actions", ["paper_id"], unique=False)
    op.create_index("ix_user_actions_user_paper", "user_actions", ["user_id", "paper_id"], unique=False)
    op.create_index("ix_user_actions_type_time", "user_actions", ["action_type", "occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_actions_type_time", table_name="user_actions")
    op.drop_index("ix_user_actions_user_paper", table_name="user_actions")
    op.drop_index("ix_user_actions_paper_id", table_name="user_actions")
    op.drop_table("user_actions")
    op.drop_index("ix_text_chunks_paper_page", table_name="text_chunks")
    op.drop_index("ix_text_chunks_paper_id", table_name="text_chunks")
    op.drop_table("text_chunks")
    op.drop_index("ix_structured_results_paper_id", table_name="structured_results")
    op.drop_table("structured_results")
    op.drop_index("ix_parse_tasks_paper_id", table_name="parse_tasks")
    op.drop_table("parse_tasks")
    op.drop_table("paper_contents")
    op.drop_table("paper_authors")
    op.drop_index("ix_papers_primary_category", table_name="papers")
    op.drop_index("ix_papers_arxiv_id", table_name="papers")
    op.drop_table("papers")
    op.drop_index("ix_authors_normalized_name", table_name="authors")
    op.drop_table("authors")

