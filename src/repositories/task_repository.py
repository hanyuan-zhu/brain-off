"""
Task repository for database operations.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Task, TaskTag
from src.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for task operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Task, db)

    async def get_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """Get tasks by status."""
        result = await self.db.execute(
            select(Task)
            .where(Task.status == status)
            .where(Task.deleted_at.is_(None))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_priority(
        self,
        priority: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """Get tasks by priority."""
        result = await self.db.execute(
            select(Task)
            .where(Task.priority == priority)
            .where(Task.deleted_at.is_(None))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def add_tag(self, task_id: UUID, tag_id: UUID) -> None:
        """Add a tag to a task."""
        # Check if relationship already exists
        result = await self.db.execute(
            select(TaskTag).where(
                and_(
                    TaskTag.task_id == task_id,
                    TaskTag.tag_id == tag_id
                )
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            task_tag = TaskTag(task_id=task_id, tag_id=tag_id)
            self.db.add(task_tag)
            await self.db.flush()

    async def remove_tag(self, task_id: UUID, tag_id: UUID) -> None:
        """Remove a tag from a task."""
        result = await self.db.execute(
            select(TaskTag).where(
                and_(
                    TaskTag.task_id == task_id,
                    TaskTag.tag_id == tag_id
                )
            )
        )
        task_tag = result.scalar_one_or_none()

        if task_tag:
            await self.db.delete(task_tag)
            await self.db.flush()

    async def remove_all_tags(self, task_id: UUID) -> None:
        """Remove all tags from a task."""
        result = await self.db.execute(
            select(TaskTag).where(TaskTag.task_id == task_id)
        )
        task_tags = result.scalars().all()

        for task_tag in task_tags:
            await self.db.delete(task_tag)
        await self.db.flush()

    async def soft_delete(self, task_id: UUID) -> None:
        """Soft delete a task."""
        from datetime import datetime, timezone

        task = await self.get_by_id(task_id)
        if task:
            task.deleted_at = datetime.now(timezone.utc)
            await self.db.flush()
