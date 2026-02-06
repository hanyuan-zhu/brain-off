import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.core.skills.tool_registry as tool_registry_module
from src.core.skills.filesystem_skill_loader import FileSystemSkillLoader
from src.services.cad_agent_tools import CAD_AGENT_TOOLS
from src.skills.supervision.setup import initialize_supervision_tools


def test_todo_skill_can_be_loaded_from_filesystem_format():
    loader = FileSystemSkillLoader(skills_path="skills")
    skill = loader.load_skill("todo")
    assert skill is not None
    assert skill.id == "todo"
    assert skill.tool_set == ["database_operation", "search"]
    assert "任务管理助手" in skill.prompt_template


def test_supervision_setup_registers_all_cad_tools(monkeypatch):
    # Reset singleton registry to avoid cross-test pollution.
    tool_registry_module._tool_registry = None

    # Keep this test independent from user env by clearing required vars.
    monkeypatch.delenv("VISION_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("VISION_MODEL_BASE_URL", raising=False)

    registry = initialize_supervision_tools()
    expected_names = {tool_def["function"]["name"] for tool_def in CAD_AGENT_TOOLS}

    assert expected_names.issubset(set(registry.tools.keys()))
    assert "inspect_region" in registry.tools
    assert registry.tools["inspect_region"]["visualization"]["calling"].startswith("检查区域")
