import pytest

from src.core.skills.tool_registry import ToolRegistry


def _schema(name: str):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}


def _standard_tool(value: int = 1):
    return {"success": True, "data": {"value": value}}


def _raw_tool(value: int = 1):
    return {"value": value}


def _error_tool():
    return {"error": "boom"}


@pytest.mark.asyncio
async def test_execute_tool_keeps_standard_envelope():
    registry = ToolRegistry()
    registry.register_tool(name="std", schema=_schema("std"), function=_standard_tool)

    result = await registry.execute_tool("std", db=None, value=7)
    assert result == {"success": True, "data": {"value": 7}}


@pytest.mark.asyncio
async def test_execute_tool_wraps_raw_payload():
    registry = ToolRegistry()
    registry.register_tool(name="raw", schema=_schema("raw"), function=_raw_tool)

    result = await registry.execute_tool("raw", db=None, value=9)
    assert result == {"success": True, "data": {"value": 9}}


@pytest.mark.asyncio
async def test_execute_tool_treats_error_dict_as_failure():
    registry = ToolRegistry()
    registry.register_tool(name="err", schema=_schema("err"), function=_error_tool)

    result = await registry.execute_tool("err", db=None)
    assert result == {"success": False, "error": "boom"}
