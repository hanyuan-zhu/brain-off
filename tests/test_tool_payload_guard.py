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
    def __init__(self):
        self.execute_count = 0

    def format_visualization(self, tool_name, arguments, stage):
        return f"{tool_name}:{stage}"

    async def execute_tool(self, tool_name, db=None, **kwargs):
        self.execute_count += 1
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


class _RepeatingLLMClient:
    def __init__(self):
        self.calls = []
        self.tool_args_history = []
        self._step = 0

    async def chat_completion(self, messages, tools=None, stream=False, **kwargs):
        self.calls.append(json.loads(json.dumps(messages, ensure_ascii=False)))
        self.tool_args_history.append(tools)
        self._step += 1

        if tools:
            tool_call = SimpleNamespace(
                id=f"repeat_{self._step}",
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
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tool_call]))]
            )

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="final answer", tool_calls=None))]
        )


@pytest.mark.asyncio
async def test_repeated_tool_rounds_use_cache_and_force_conclusion():
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    registry = _FakeToolRegistry()
    llm = _RepeatingLLMClient()
    agent.llm_client = llm
    agent.tool_registry = registry

    state = AgentState()
    messages = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "run"},
    ]
    tools = [{"type": "function", "function": {"name": "inspect_region"}}]

    result = await agent._agent_loop(state=state, messages=messages, tools=tools)
    assert result["text"] == "final answer"
    assert registry.execute_count == 1
    assert any(not tool_arg for tool_arg in llm.tool_args_history)


class _BudgetLLMClient:
    def __init__(self):
        self.tool_args_history = []
        self._seq = 0

    async def chat_completion(self, messages, tools=None, stream=False, **kwargs):
        self.tool_args_history.append(tools)

        if tools:
            self._seq += 1
            tool_call = SimpleNamespace(
                id=f"budget_{self._seq}",
                type="function",
                function=SimpleNamespace(
                    name="inspect_region",
                    arguments=json.dumps(
                        {
                            "file_path": "fake.dxf",
                            "x": self._seq * 1000,
                            "y": 0,
                            "width": 1000,
                            "height": 1000,
                        }
                    ),
                ),
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tool_call]))]
            )

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="budget final", tool_calls=None))]
        )


@pytest.mark.asyncio
async def test_tool_call_budget_forces_conclusion():
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    agent.max_tool_calls_per_turn = 3
    agent.max_iterations = 5
    registry = _FakeToolRegistry()
    llm = _BudgetLLMClient()
    agent.llm_client = llm
    agent.tool_registry = registry

    state = AgentState()
    messages = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "run"},
    ]
    tools = [{"type": "function", "function": {"name": "inspect_region"}}]

    result = await agent._agent_loop(state=state, messages=messages, tools=tools)
    assert result["text"] == "budget final"
    assert registry.execute_count > 3
    advisory_types = {item["type"] for item in result.get("loop_advisories", [])}
    assert "tool_budget_warning" in advisory_types
    assert any(not tool_arg for tool_arg in llm.tool_args_history)


def test_append_detailed_trace_log_includes_images_and_iteration(tmp_path):
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    agent.trace_log_path = tmp_path / "work_log_detailed.md"

    loop_result = {
        "text": "final answer summary",
        "iteration_traces": [
            {
                "iteration": 1,
                "assistant_plan": "先看全局，再看局部",
                "reasoning": "优先检查文字密集区域",
                "summary": "get_cad_metadata(ok) -> inspect_region(ok)",
                "advisories": [],
                "tool_calls": [
                    {
                        "name": "inspect_region",
                        "args": {"x": 1, "y": 2, "width": 3, "height": 4},
                        "cached": False,
                        "result_summary": {
                            "success": True,
                            "highlights": ["bbox: (1,2)+3x4"],
                            "image_paths": ["workspace/rendered/demo.png"],
                        },
                    }
                ],
            }
        ],
        "loop_advisories": [
            {
                "iteration": 1,
                "type": "tool_budget_warning",
                "message": "budget warning",
            }
        ],
    }

    path = agent._append_detailed_trace_log(
        session_id="12345678-0000-0000-0000-000000000000",
        user_message="请预审项目",
        skill_id="supervision",
        loop_result=loop_result,
    )

    assert path is not None
    content = (tmp_path / "work_log_detailed.md").read_text(encoding="utf-8")
    assert "Iteration 1" in content
    assert "请预审项目" in content
    assert "![iter1-tool1](./rendered/demo.png)" in content
    assert "budget warning" in content


def test_summarize_tool_result_handles_nested_envelope():
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    nested_result = {
        "success": True,
        "data": {
            "success": True,
            "data": {
                "image_path": "workspace/rendered/nested.png",
                "region_info": {
                    "bbox": {"x": 10, "y": 20, "width": 30, "height": 40},
                },
                "entity_summary": {"total_count": 5},
                "key_content": {"text_count": 2},
            },
        },
    }

    summary = agent._summarize_tool_result("inspect_region", nested_result)
    assert summary["success"] is True
    assert "workspace/rendered/nested.png" in summary["image_paths"]
    assert any("bbox: (10, 20) + 30x40" in item for item in summary["highlights"])
    assert any("entity_total: 5" in item for item in summary["highlights"])
    assert any("text_count: 2" in item for item in summary["highlights"])


def test_sanitize_tool_result_handles_nested_base64_payload():
    agent = MemoryDrivenAgent(db=_DummyDB(), fixed_skill_id="supervision")
    nested_result = {
        "success": True,
        "data": {
            "success": True,
            "data": {
                "image_path": "workspace/rendered/nested.png",
                "image_base64": "X" * 60000,
                "key_content": {"texts": [{"text": "demo"}] * 30, "text_count": 30},
            },
        },
    }

    sanitized = agent._sanitize_tool_result("inspect_region", nested_result)
    assert sanitized["success"] is True
    assert "data" in sanitized
    assert "image_base64" not in sanitized["data"]
    assert sanitized["data"].get("image_base64_omitted") is True
    assert sanitized["data"].get("image_base64_chars") == 60000
    assert len(sanitized["data"]["key_content"]["texts"]) == 20
    assert sanitized["data"]["key_content"]["texts_truncated"] == 10
