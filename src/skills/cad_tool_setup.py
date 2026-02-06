"""
Shared CAD tool registration helpers for skill setup modules.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.skills.tool_registry import get_tool_registry
from src.services.cad_agent_tools import (
    CAD_AGENT_TOOLS,
    append_to_file,
    convert_dwg_to_dxf,
    extract_cad_entities,
    get_cad_metadata,
    inspect_region,
    list_files,
    read_file,
    write_file,
)


CAD_TOOL_FUNCTIONS = {
    "get_cad_metadata": get_cad_metadata,
    "inspect_region": inspect_region,
    "extract_cad_entities": extract_cad_entities,
    "convert_dwg_to_dxf": convert_dwg_to_dxf,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "append_to_file": append_to_file,
}


def _check_vision_environment(skill_label: str) -> bool:
    required_vars = {
        "VISION_MODEL_API_KEY": "Kimi/Vision model API key",
        "VISION_MODEL_BASE_URL": "Vision model API base URL",
    }

    missing_vars = [
        f"  - {var_name}: {description}"
        for var_name, description in required_vars.items()
        if not os.getenv(var_name)
    ]

    if missing_vars:
        print(f"\n⚠️  [{skill_label} Skill] Missing required environment variables:")
        for var in missing_vars:
            print(var)
        print("\nPlease set these variables in your .env file")
        return False

    return True


def _load_skill_visualizations(skill_id: str) -> Dict[str, Dict[str, str]]:
    """
    Read visualization templates from skills/<skill_id>/config.json.
    """
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "skills" / skill_id / "config.json"
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        visualizations = config.get("visualizations")
        return visualizations if isinstance(visualizations, dict) else {}
    except Exception as e:
        print(f"⚠️  Failed to load visualizations from {config_path}: {e}")
        return {}


def register_cad_skill_tools(
    skill_id: str,
    skill_label: str,
    fallback_visualizations: Optional[Dict[str, Dict[str, str]]] = None,
):
    """
    Register shared CAD tools for one skill.
    """
    if not _check_vision_environment(skill_label):
        print(f"⚠️  [{skill_label} Skill] Environment not fully configured; continuing registration")

    registry = get_tool_registry()

    visualizations = dict(fallback_visualizations or {})
    visualizations.update(_load_skill_visualizations(skill_id))

    registered_count = 0
    for tool_def in CAD_AGENT_TOOLS:
        tool_name = tool_def["function"]["name"]
        tool_func = CAD_TOOL_FUNCTIONS.get(tool_name)
        if not tool_func:
            continue

        registry.register_tool(
            name=tool_name,
            schema=tool_def,
            function=tool_func,
            visualization=visualizations.get(tool_name),
        )
        registered_count += 1

    print(f"[{skill_label} Skill] Registered {registered_count} tools")
    return registry
