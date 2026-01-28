"""
Search service with semantic search using pgvector.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Task
from src.services.embedding_service import get_embedding_service


class SearchService:
    """Service for semantic search using vector embeddings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = get_embedding_service()

    async def search_tasks_semantic(
        self,
        query: str,
        limit: int = 20,
        status_filter: Optional[List[str]] = None,
        priority_filter: Optional[List[str]] = None
    ) -> List[Task]:
        """
        Search tasks using semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            status_filter: Filter by task status
            priority_filter: Filter by task priority

        Returns:
            List of tasks ordered by relevance
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate(query)

        # Build query
        stmt = select(Task).where(Task.deleted_at.is_(None))

        # Apply filters
        if status_filter:
            stmt = stmt.where(Task.status.in_(status_filter))
        if priority_filter:
            stmt = stmt.where(Task.priority.in_(priority_filter))

        # Order by cosine similarity
        stmt = stmt.order_by(
            Task.embedding.cosine_distance(query_embedding)
        ).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
