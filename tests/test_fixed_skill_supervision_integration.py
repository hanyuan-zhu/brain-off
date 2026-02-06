import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.core.skills.tool_registry as tool_registry_module
from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.skills.initialize import initialize_all_tools


class _DummyDB:
    """No-op DB object for fixed-skill integration tests."""


class _FakeLLMClient:
    def __init__(self):
        self.calls = []

    async def chat_completion(self, messages, tools=None, stream=False, **kwargs):
        self.calls.append({
            "messages": messages,
            "tools": tools or [],
            "stream": stream,
            "kwargs": kwargs,
        })
        message = SimpleNamespace(content="集成测试响应", tool_calls=None)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeEmbeddingService:
    async def generate(self, text: str):
        return [0.01, 0.02, 0.03]


@pytest.mark.asyncio
async def test_fixed_skill_supervision_pipeline_loads_skill_prompt_and_tools(monkeypatch):
    # 1) Reset global tool registry and register tools exactly as app startup does.
    tool_registry_module._tool_registry = None
    initialize_all_tools()

    # 2) Build agent in fixed skill mode (same route as: chat.py --skill supervision).
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    fake_llm = _FakeLLMClient()
    agent.embedding_service = _FakeEmbeddingService()

    # Override LLM initialization to avoid network and ensure deterministic tool capture.
    def _fake_init_llm(_skill_config=None):
        agent.llm_client = fake_llm

    monkeypatch.setattr(agent, "_initialize_llm_client", _fake_init_llm)

    result = await agent.process_message("请分析图纸", session_id=None)

    assert result["success"] is True
    assert result["metadata"]["skill_id"] == "supervision"
    assert result["text"] == "集成测试响应"
    assert result["iterations"] == 1

    # 3) Verify tool schemas sent to LLM match skill config (not default tools).
    assert len(fake_llm.calls) == 1
    sent_tools = fake_llm.calls[0]["tools"]
    sent_tool_names = {item["function"]["name"] for item in sent_tools}

    with open("skills/supervision/config.json", "r", encoding="utf-8") as f:
        supervision_cfg = json.load(f)
    expected_tool_names = set(supervision_cfg["tools"])

    assert sent_tool_names == expected_tool_names
    assert "inspect_region" in sent_tool_names
    assert "database_operation" not in sent_tool_names
