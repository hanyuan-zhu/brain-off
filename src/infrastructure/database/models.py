"""
SQLAlchemy models for the AI Task Manager application.

模块化架构：
- Core: Skill, MemSource, Fact (核心系统)
- Todo Skill: Task, Tag, TaskTag (Todo 技能的数据对象)
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey,
    CheckConstraint, Index, func, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# ============================================================================
# Core System Models (核心系统模型)
# ============================================================================

class Skill(Base):
    """Skill definition model - stores skill metadata and configuration."""
    __tablename__ = "skills"

    # Primary key
    id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Basic fields
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    # AI fields
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1024), nullable=True)

    # Configuration
    tool_set: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Temporal fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Indexes
    __table_args__ = (
        Index("idx_skills_name", "name"),
    )


class MemSource(Base):
    """Memory source model - stores conversation history for compression."""
    __tablename__ = "mem_source"

    # Primary key
    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Session info
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tool_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # AI fields
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1024), nullable=True)

    # Temporal fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_mem_source_session", "session_id"),
        Index("idx_mem_source_created", "created_at"),
    )


class Fact(Base):
    """Fact model - stores extracted facts from conversations."""
    __tablename__ = "facts"

    # Primary key
    fact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Content
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[Optional[list]] = mapped_column(ARRAY(Integer), nullable=True)

    # Classification
    fact_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")

    # AI fields
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1024), nullable=True)

    # Temporal fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_facts_domain", "domain"),
        Index("idx_facts_type", "fact_type"),
    )


# ============================================================================
# Todo Skill Models (Todo 技能的数据对象)
# ============================================================================

class Task(Base):
    """Task model - data object for Todo skill."""
    __tablename__ = "tasks"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Basic fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="brainstorm", nullable=False)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    energy_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Temporal fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI-enhanced fields
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1024), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}")

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tags = relationship("TaskTag", back_populates="task", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('brainstorm', 'inbox', 'active', 'waiting', 'someday', 'completed', 'archived')",
            name="valid_status"
        ),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_due_date", "due_date"),
        Index("idx_tasks_metadata", "metadata", postgresql_using="gin"),
    )


class Tag(Base):
    """Tag model - for categorizing tasks."""
    __tablename__ = "tags"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Basic fields
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    tasks = relationship("TaskTag", back_populates="tag", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_tags_name", "name"),
    )


class TaskTag(Base):
    """Junction table for many-to-many relationship between tasks and tags."""
    __tablename__ = "task_tags"

    # Composite primary key
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("Task", back_populates="tags")
    tag = relationship("Tag", back_populates="tasks")

