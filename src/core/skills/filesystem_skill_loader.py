"""
Filesystem-based skill loader.

Loads skills from the filesystem (skills/ folder) instead of database.
Each skill is a folder containing:
- skill.md: The prompt template
- config.json: Configuration (tools, model, metadata)
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.infrastructure.database.models import Skill
from src.core.memory.embedding_service import EmbeddingService


@dataclass
class SkillConfig:
    """Skill configuration from config.json"""
    id: str
    name: str
    tools: List[str]
    version: Optional[str] = None
    description: Optional[str] = None
    model: Optional[Dict[str, Any]] = None
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None


class FileSystemSkillLoader:
    """Loads skills from filesystem"""

    def __init__(
        self,
        skills_path: str = "skills",
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.skills_path = Path(skills_path)
        self.embedding_service = embedding_service

    def load_all_skills(self) -> List[Skill]:
        """Load all skills from filesystem"""
        if not self.skills_path.exists():
            return []

        skills = []
        for skill_dir in self.skills_path.iterdir():
            if skill_dir.is_dir():
                try:
                    skill = self.load_skill(skill_dir.name)
                    if skill:
                        skills.append(skill)
                except Exception as e:
                    print(f"Warning: Failed to load skill from {skill_dir}: {e}")

        return skills

    def load_skill(self, skill_id: str) -> Optional[Skill]:
        """Load a single skill by ID"""
        skill_dir = self.skills_path / skill_id
        if not skill_dir.exists() or not skill_dir.is_dir():
            return None

        # Load config.json
        config_path = skill_dir / "config.json"
        if not config_path.exists():
            raise ValueError(f"config.json not found in {skill_dir}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        config = SkillConfig(**config_data)

        # Skip if disabled
        if not config.enabled:
            return None

        # Load skill.md
        skill_md_path = skill_dir / "skill.md"
        if not skill_md_path.exists():
            raise ValueError(f"skill.md not found in {skill_dir}")

        with open(skill_md_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        return self._create_skill_object(config, prompt_template)

    def _create_skill_object(self, config: SkillConfig, prompt_template: str) -> Skill:
        """Create a Skill object from config and prompt"""
        # Generate embedding if service is available
        embedding = None
        if self.embedding_service:
            embedding = self.embedding_service.generate(prompt_template)

        # Create Skill object (matches database model structure)
        skill = Skill(
            id=config.id,
            name=config.name,
            prompt_template=prompt_template,
            tool_set=config.tools,
            embedding=embedding
        )

        # Attach additional metadata as attributes
        skill.version = config.version
        skill.description = config.description
        skill.model_config = config.model
        skill.metadata = config.metadata

        return skill

    def list_skill_ids(self) -> List[str]:
        """List all available skill IDs in filesystem"""
        if not self.skills_path.exists():
            return []

        skill_ids = []
        for skill_dir in self.skills_path.iterdir():
            if skill_dir.is_dir() and (skill_dir / "config.json").exists():
                skill_ids.append(skill_dir.name)

        return skill_ids

    def skill_exists(self, skill_id: str) -> bool:
        """Check if a skill exists in filesystem"""
        skill_dir = self.skills_path / skill_id
        return (
            skill_dir.exists()
            and skill_dir.is_dir()
            and (skill_dir / "config.json").exists()
            and (skill_dir / "skill.md").exists()
        )

    def sync_to_database(self, db_session) -> Dict[str, Any]:
        """
        Sync all filesystem skills to database.
        Returns a summary of the sync operation.
        """
        from sqlalchemy import select

        summary = {
            "created": [],
            "updated": [],
            "skipped": [],
            "errors": []
        }

        skills = self.load_all_skills()

        for skill in skills:
            try:
                # Check if skill exists in database
                stmt = select(Skill).where(Skill.id == skill.id)
                existing = db_session.execute(stmt).scalar_one_or_none()

                if existing is None:
                    # Create new skill
                    db_session.add(skill)
                    summary["created"].append(skill.id)
                else:
                    # Update existing skill
                    existing.name = skill.name
                    existing.prompt_template = skill.prompt_template
                    existing.tool_set = skill.tool_set
                    existing.model_config = skill.model_config
                    existing.embedding = skill.embedding
                    summary["updated"].append(skill.id)

            except Exception as e:
                summary["errors"].append({"skill_id": skill.id, "error": str(e)})

        db_session.commit()
        return summary
