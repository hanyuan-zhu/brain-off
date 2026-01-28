"""
Conversation repository for database operations.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Conversation
from src.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Conversation, db)

    async def get_by_task(
        self,
        task_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[Conversation]:
        """Get conversations for a specific task."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.task_id == task_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
