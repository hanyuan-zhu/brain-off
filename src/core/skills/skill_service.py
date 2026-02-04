"""
Skill Service - 管理技能的检索和 CRUD 操作
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.infrastructure.database.models import Skill
from src.core.memory.embedding_service import EmbeddingService
from src.core.skills.filesystem_skill_loader import FileSystemSkillLoader


class SkillService:
    """技能管理服务"""

    def __init__(
        self,
        db: AsyncSession,
        enable_filesystem: bool = True,
        skills_path: str = "skills"
    ):
        self.db = db
        self.embedding_service = EmbeddingService()
        self.enable_filesystem = enable_filesystem

        # Initialize filesystem loader if enabled
        self.fs_loader = None
        if enable_filesystem:
            self.fs_loader = FileSystemSkillLoader(
                skills_path=skills_path,
                embedding_service=self.embedding_service
            )

    async def retrieve_skills(
        self,
        query_embedding: List[float],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于 embedding 检索最相关的 skills

        Args:
            query_embedding: 查询的 embedding 向量
            top_k: 返回结果数量

        Returns:
            技能列表，每个技能包含 id, name, prompt_template
        """
        # 使用向量相似度检索
        query = text("""
            SELECT
                id,
                name,
                prompt_template,
                tool_set,
                1 - (embedding <=> :query_embedding) as similarity
            FROM skills
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """)

        result = await self.db.execute(
            query,
            {
                "query_embedding": str(query_embedding),
                "top_k": top_k
            }
        )

        skills = []
        for row in result:
            skills.append({
                "id": row.id,
                "name": row.name,
                "prompt_template": row.prompt_template,
                "tool_set": row.tool_set,
                "similarity": row.similarity
            })

        return skills

    async def get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        """
        根据 ID 获取 skill
        优先从文件系统加载，如果不存在则从数据库加载

        Args:
            skill_id: 技能 ID

        Returns:
            Skill 对象，如果不存在则返回 None
        """
        # Try filesystem first if enabled
        if self.enable_filesystem and self.fs_loader:
            if self.fs_loader.skill_exists(skill_id):
                return self.fs_loader.load_skill(skill_id)

        # Fallback to database
        result = await self.db.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        return result.scalar_one_or_none()

    async def create_skill(
        self,
        skill_id: str,
        name: str,
        prompt_template: str,
        tool_set: List[str]
    ) -> Skill:
        """
        创建新 skill（自动生成 embedding）

        Args:
            skill_id: 技能 ID
            name: 技能名称
            prompt_template: Prompt 模板
            tool_set: 工具集列表

        Returns:
            创建的 Skill 对象
        """
        # 生成 embedding
        embedding = await self.embedding_service.generate(prompt_template)

        # 创建 skill
        skill = Skill(
            id=skill_id,
            name=name,
            prompt_template=prompt_template,
            embedding=embedding,
            tool_set=tool_set
        )

        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)

        return skill

    async def update_skill(
        self,
        skill_id: str,
        prompt_template: str
    ) -> Optional[Skill]:
        """
        更新 skill（自动重新生成 embedding）

        Args:
            skill_id: 技能 ID
            prompt_template: 新的 Prompt 模板

        Returns:
            更新后的 Skill 对象，如果不存在则返回 None
        """
        skill = await self.get_skill_by_id(skill_id)
        if not skill:
            return None

        # 重新生成 embedding
        embedding = await self.embedding_service.embed(prompt_template)

        # 更新
        skill.prompt_template = prompt_template
        skill.embedding = embedding

        await self.db.commit()
        await self.db.refresh(skill)

        return skill

    async def sync_filesystem_to_db(self) -> Dict[str, Any]:
        """
        将文件系统中的skills同步到数据库

        Returns:
            同步操作的摘要信息
        """
        if not self.enable_filesystem or not self.fs_loader:
            return {"error": "Filesystem loading is not enabled"}

        return self.fs_loader.sync_to_database(self.db)
