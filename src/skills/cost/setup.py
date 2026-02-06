"""
Cost Skill tool initialization.
"""

from src.skills.cad_tool_setup import register_cad_skill_tools


def initialize_cost_tools():
    """Initialize Cost Skill CAD tools."""
    return register_cad_skill_tools(
        skill_id="cost",
        skill_label="Cost",
    )
