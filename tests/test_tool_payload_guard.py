import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.agent.memory_driven_agent import MemoryDrivenAgent
from src.core.agent.state import AgentState


class _DummyDB:
    pass


class _FakeToolRegistry:
    def format_visualization(self, tool_name, arguments, stage):
        return f"{tool_name}:{stage}"

    async def execute_tool(self, tool_name, db=None, **kwargs):
        return {
            "success": True,
            "data": {
                "image_path": "workspace/rendered/fake.png",
                "image_base64": "X" * 500000,
                "entity_summary": {"total_count": 10},
                "key_content": {"texts": [{"text": "a"}] * 30, "text_count": 30},
            },
        }


class _FakeLLMClient:
    def __init__(self):
        self.calls = []
        self._step = 0

    async def chat_completion(self, messages, tools=None, stream=False, **kwargs):
        self.calls.append(json.loads(json.dumps(messages, ensure_ascii=False)))
        self._step += 1

        if self._step == 1:
            tool_call = SimpleNamespace(
                id="tool_1",
                type="function",
                function=SimpleNamespace(
                    name="inspect_region",
                    arguments=json.dumps(
                        {
                            "file_path": "fake.dxf",
                            "x": 0,
                            "y": 0,
                            "width": 1000,
                            "height": 1000,
                        }
                    ),
                ),
            )
            message = SimpleNamespace(content="", tool_calls=[tool_call])
        else:
            message = SimpleNamespace(content="done", tool_calls=None)

        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.asyncio
async def test_large_tool_payload_is_trimmed_before_next_llm_call():
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    agent.llm_client = _FakeLLMClient()
    agent.tool_registry = _FakeToolRegistry()

    state = AgentState()
    messages = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "run"},
    ]

    result = await agent._agent_loop(state=state, messages=messages, tools=[])
    assert result["text"] == "done"
    assert len(agent.llm_client.calls) == 2

    second_call_messages = agent.llm_client.calls[1]
    tool_messages = [msg for msg in second_call_messages if msg.get("role") == "tool"]
    assert len(tool_messages) == 1

    tool_content = tool_messages[0]["content"]
    assert "image_base64_omitted" in tool_content
    assert "image_base64_chars" in tool_content
    assert "X" * 1000 not in tool_content
    assert len(tool_content) < agent.max_tool_result_chars + 2000

    state_tool_messages = [msg for msg in state.conversation_history if msg.role == "tool"]
    assert len(state_tool_messages) == 1
    assert "image_base64_omitted" in state_tool_messages[0].content
