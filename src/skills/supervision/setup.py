"""
Supervision Skill tool initialization.
"""

from src.skills.cad_tool_setup import register_cad_skill_tools


def initialize_supervision_tools():
    """Initialize Supervision Skill CAD tools."""
    return register_cad_skill_tools(
        skill_id="supervision",
        skill_label="Supervision",
    )
