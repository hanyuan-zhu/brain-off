"""
Tag repository for database operations.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Tag
from src.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    """Repository for tag operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Tag, db)

    async def get_by_name(self, name: str) -> Optional[Tag]:
        """Get tag by name."""
        result = await self.db.execute(
            select(Tag).where(Tag.name == name)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        name: str,
        color: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tag:
        """Get existing tag or create new one."""
        tag = await self.get_by_name(name)
        if tag:
            return tag

        return await self.create(
            name=name,
            color=color,
            description=description
        )

    async def increment_usage(self, tag_id: UUID) -> None:
        """Increment tag usage count."""
        await self.db.execute(
            update(Tag)
            .where(Tag.id == tag_id)
            .values(usage_count=Tag.usage_count + 1)
        )
        await self.db.flush()

    async def get_popular_tags(self, limit: int = 10) -> List[Tag]:
        """Get most popular tags by usage count."""
        result = await self.db.execute(
            select(Tag)
            .order_by(Tag.usage_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
