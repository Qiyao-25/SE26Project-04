from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.model.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Paper(TimestampMixin, Base):
    __tablename__ = "papers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arxiv_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primary_category: Mapped[str | None] = mapped_column(String(128), index=True)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    ingest_status: Mapped[str] = mapped_column(String(32), nullable=False, default="metadata_only", server_default="metadata_only")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authors: Mapped[list["PaperAuthor"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    parse_tasks: Mapped[list["ParseTask"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    structured_results: Mapped[list["StructuredResult"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    content: Mapped["PaperContent | None"] = relationship(back_populates="paper", uselist=False, cascade="all, delete-orphan")
    chunks: Mapped[list["TextChunk"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    user_actions: Mapped[list["UserAction"]] = relationship(back_populates="paper")


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    orcid: Mapped[str | None] = mapped_column(String(64), unique=True)
    papers: Mapped[list["PaperAuthor"]] = relationship(back_populates="author", cascade="all, delete-orphan")


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    author_order: Mapped[int] = mapped_column(Integer, nullable=False)
    paper: Mapped[Paper] = relationship(back_populates="authors")
    author: Mapped[Author] = relationship(back_populates="papers")


class PaperContent(Base):
    __tablename__ = "paper_contents"
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paper: Mapped[Paper] = relationship(back_populates="content")


class ParseTask(Base):
    __tablename__ = "parse_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    paper: Mapped[Paper] = relationship(back_populates="parse_tasks")


class StructuredResult(Base):
    __tablename__ = "structured_results"
    __table_args__ = (UniqueConstraint("paper_id", "result_type", "version", name="uq_result_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    parse_task_id: Mapped[int | None] = mapped_column(ForeignKey("parse_tasks.id"))
    result_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None]
    paper: Mapped[Paper] = relationship(back_populates="structured_results")


class TextChunk(Base):
    __tablename__ = "text_chunks"
    __table_args__ = (UniqueConstraint("paper_id", "chunk_id", name="uq_chunk_per_paper"), Index("ix_text_chunks_paper_page", "paper_id", "page_no"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    page_no: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    paper: Mapped[Paper] = relationship(back_populates="chunks")


class UserAction(Base):
    __tablename__ = "user_actions"
    __table_args__ = (Index("ix_user_actions_user_paper", "user_id", "paper_id"), Index("ix_user_actions_type_time", "action_type", "occurred_at"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paper: Mapped[Paper] = relationship(back_populates="user_actions")

