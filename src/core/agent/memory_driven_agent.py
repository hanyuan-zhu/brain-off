"""
记忆驱动 Agent - 基于新架构重写

核心特性：
1. Embedding-based skill 检索
2. LLM 过滤 skills 和 facts
3. 动态工具挂载
4. 对话压缩
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
import json
import asyncio
import copy
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.agent.state import AgentState, get_session_manager
from src.infrastructure.llm.deepseek_client import DeepSeekClient
from src.infrastructure.llm.unified_client import create_llm_client
from src.core.memory.embedding_service import EmbeddingService
from src.core.memory.online_memory_adapter import OnlineMemoryAdapter
from src.core.skills.skill_service import SkillService
from src.core.skills.filter_service import FilterService
from src.core.skills.tool_registry import get_tool_registry
from src.core.utils.performance_tracker import PerformanceTracker
from src.core.utils.debug import debug_print


class MemoryDrivenAgent:
    """记忆驱动的统一 Agent"""

    def __init__(self, db: AsyncSession, use_reasoner: bool = False, fixed_skill_id: Optional[str] = None):
        """
        初始化 Agent

        Args:
            db: 数据库会话
            use_reasoner: 是否使用 reasoner 模式
            fixed_skill_id: 固定使用的 skill ID，如果提供则跳过 LLM 自动选择
        """
        self.db = db
        self.session_manager = get_session_manager()
        self.max_iterations = 20
        # Keep tool payloads compact before sending back to LLM to avoid token overflow.
        self.max_tool_result_chars = 40000
        # Soft budget hint per user turn to reduce accidental tool loops.
        self.max_tool_calls_per_turn = 14
        # Soft loop advisory: same tool+args repeated this many times will trigger a warning hint.
        self.loop_review_repeat_threshold = 3
        # Auto trace worklog path for detailed per-iteration execution record.
        self.trace_log_path = Path("workspace/work_log_detailed.md")
        self.fixed_skill_id = fixed_skill_id
        self.use_reasoner = use_reasoner

        # 服务层
        self.embedding_service = EmbeddingService()
        self.skill_service = SkillService(db)
        self.filter_service = FilterService()

        # 线上记忆适配器
        self.online_memory_adapter = OnlineMemoryAdapter(enabled=False)  # 临时禁用线上记忆

        # 工具注册表
        self.tool_registry = get_tool_registry()

        # LLM 客户端（延迟初始化，根据 skill 配置）
        self.llm_client = None

    def _initialize_llm_client(self, skill_config: Optional[Dict[str, Any]] = None):
        """
        根据 skill 配置初始化 LLM 客户端

        Args:
            skill_config: skill 配置（包含 model 和 metadata）
        """
        self.llm_client = create_llm_client(
            skill_config=skill_config,
            use_reasoner=self.use_reasoner
        )

        # 打印使用的模型信息
        provider = "Kimi" if self.llm_client.supports_vision else "DeepSeek"
        debug_print(f"[Agent] 使用模型: {provider} ({self.llm_client.model})")

    async def process_message(
        self,
        user_message: str,
        session_id: Optional[UUID] = None,
        stream_callback=None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        处理用户消息（新架构）

        Args:
            user_message: 用户消息
            session_id: 会话 ID
            stream_callback: 流式输出回调
            progress_callback: 进度回调函数 (progress, desc)

        Returns:
            处理结果
        """
        # 创建性能追踪器
        tracker = PerformanceTracker(user_query=user_message)

        # 获取或创建会话
        tracker.start_sync_step("初始化会话")
        if progress_callback is not None:
            progress_value, desc = tracker.get_progress()
            progress_callback(progress_value, desc)

        if session_id:
            # 将字符串 session_id 转换为 UUID
            try:
                session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
                state = self.session_manager.get_session(session_uuid)
            except (ValueError, AttributeError):
                state = None

            if not state:
                state = self.session_manager.create_session()
        else:
            state = self.session_manager.create_session()

        # 添加用户消息
        state.add_message("user", user_message)
        tracker.end_sync_step("初始化会话")

        try:
            # 1. 生成 query embedding
            tracker.start_sync_step("生成查询向量")
            if progress_callback is not None:
                progress_value, desc = tracker.get_progress()
                progress_callback(progress_value, desc)
            query_embedding = await self.embedding_service.generate(user_message)
            tracker.end_sync_step("生成查询向量")

            # 2. 检索 skills（如果有固定 skill 则跳过）
            if self.fixed_skill_id:
                # 固定 skill 模式：直接加载指定 skill
                tracker.start_sync_step("加载固定技能")
                if progress_callback is not None:
                    progress_value, desc = tracker.get_progress()
                    progress_callback(progress_value, desc)

                selected_skill = await self.skill_service.get_skill_by_id(self.fixed_skill_id)
                if not selected_skill:
                    error_msg = f"错误：找不到 skill '{self.fixed_skill_id}'"
                    debug_print(error_msg)
                    tracker.end_sync_step("加载固定技能", error=error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "session_id": str(state.session_id)
                    }

                debug_print(f"[DEBUG] 使用固定 skill: {selected_skill.name} (ID: {selected_skill.id})")
                filter_result = {"skill_id": self.fixed_skill_id, "fact_ids": [], "reasoning": "使用固定 skill 模式"}

                # 初始化 LLM 客户端（根据 skill 配置）
                skill_config = {
                    "model": selected_skill.model_config,
                    "metadata": selected_skill.metadata
                }
                self._initialize_llm_client(skill_config)

                tracker.end_sync_step("加载固定技能")

                # 仍然执行线上记忆召回
                tracker.start_async_step("线上记忆召回")
                if progress_callback is not None:
                    progress_value, desc = tracker.get_progress()
                    progress_callback(progress_value, desc)
                try:
                    online_memories = await self.online_memory_adapter.recall_memories(query=user_message, top_k=5)
                    tracker.end_async_step("线上记忆召回")
                except Exception as e:
                    debug_print(f"⚠️ 线上记忆召回失败: {e}")
                    tracker.end_async_step("线上记忆召回", error=str(e))
                    online_memories = []
            else:
                # 原有逻辑：LLM 自动选择
                tracker.start_sync_step("检索技能")
                if progress_callback is not None:
                    progress_value, desc = tracker.get_progress()
                    progress_callback(progress_value, desc)
                candidate_skills = await self.skill_service.retrieve_skills(
                    query_embedding, top_k=3
                )
                tracker.end_sync_step("检索技能")

                # 3. 【并行优化】同时执行线上记忆召回和 LLM 过滤 skills
                tracker.start_async_step("线上记忆召回")
                tracker.start_sync_step("LLM过滤技能")
                if progress_callback is not None:
                    progress_value, desc = tracker.get_progress()
                    progress_callback(progress_value, desc)

                # 并行执行两个任务（带异常处理）
                try:
                    online_memories, filter_result = await asyncio.gather(
                        self.online_memory_adapter.recall_memories(query=user_message, top_k=5),
                        self.filter_service.filter_skills_and_facts(
                            user_query=user_message,
                            candidate_skills=candidate_skills,
                            candidate_facts=[]  # 不再使用本地 facts
                        )
                    )
                    tracker.end_async_step("线上记忆召回")
                    tracker.end_sync_step("LLM过滤技能")
                except Exception as e:
                    # 如果线上记忆召回失败，使用空列表继续
                    debug_print(f"⚠️ 线上记忆召回或过滤失败: {e}")
                    tracker.end_async_step("线上记忆召回", error=str(e))

                    # 重新执行 LLM 过滤（如果失败的话）
                    try:
                        filter_result = await self.filter_service.filter_skills_and_facts(
                            user_query=user_message,
                            candidate_skills=candidate_skills,
                            candidate_facts=[]
                        )
                        tracker.end_sync_step("LLM过滤技能")
                    except Exception as filter_error:
                        debug_print(f"⚠️ LLM 过滤失败: {filter_error}")
                        tracker.end_sync_step("LLM过滤技能", error=str(filter_error))
                        # 使用默认值
                        filter_result = {"skill_id": None, "fact_ids": []}

                    online_memories = []

            # 4. 根据 skill_id 获取工具集和 prompt
            tracker.start_sync_step("准备工具和Prompt")
            if progress_callback is not None:
                progress_value, desc = tracker.get_progress()
                progress_callback(progress_value, desc)
            skill_prompt = ""
            tools = []
            skill_config = None

            if filter_result["skill_id"]:
                skill = await self.skill_service.get_skill_by_id(filter_result["skill_id"])
                if skill:
                    tools = self.tool_registry.get_tools_by_names(skill.tool_set)
                    skill_prompt = skill.prompt_template
                    skill_config = {
                        "model": skill.model_config,
                        "metadata": skill.metadata
                    }

            # 初始化 LLM 客户端（如果还未初始化）
            if self.llm_client is None:
                self._initialize_llm_client(skill_config)

            if not tools:
                tools = self.tool_registry.get_default_tools()

            # 5. 构建 messages（只使用线上记忆）
            messages = self._build_messages(state, skill_prompt, online_memories)

            # 记录上下文内容到 tracker
            tracker.set_context_content({
                "skill_prompt": skill_prompt,
                "online_memories": online_memories,
                "conversation_history": [
                    {"role": msg.role, "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content}
                    for msg in state.conversation_history
                ],
                "system_prompt_length": len(messages[0]["content"]) if messages else 0,
                "total_messages": len(messages)
            })

            tracker.end_sync_step("准备工具和Prompt")

            # 8. 执行 agent loop
            tracker.start_sync_step("LLM生成响应")
            if progress_callback is not None:
                progress_value, desc = tracker.get_progress()
                progress_callback(progress_value, desc)
            result = await self._agent_loop(
                state=state,
                messages=messages,
                tools=tools,
                stream_callback=stream_callback
            )
            tracker.end_sync_step("LLM生成响应")

            trace_log_file = self._append_detailed_trace_log(
                session_id=str(state.session_id),
                user_message=user_message,
                skill_id=filter_result.get("skill_id"),
                loop_result=result,
            )

            # 9. 【冗余挂载】存储对话到线上记忆（真正的异步，不阻塞返回）
            async def store_to_online_background():
                """后台存储到线上记忆"""
                tracker.start_async_step("线上记忆存储")
                try:
                    await self.online_memory_adapter.store_message(
                        text=user_message,
                        user_id="default_user",
                        session_id=str(state.session_id),
                        role="user"
                    )
                    await self.online_memory_adapter.store_message(
                        text=result["text"],
                        user_id="default_user",
                        session_id=str(state.session_id),
                        role="assistant"
                    )
                    tracker.end_async_step("线上记忆存储")
                except Exception as e:
                    tracker.end_async_step("线上记忆存储", error=str(e))

            # 创建后台任务，不等待完成
            asyncio.create_task(store_to_online_background())

            # 完成追踪（主流程）
            tracker.complete(response=result["text"])
            if progress_callback is not None:
                progress_callback(1.0, "✅ 完成")

            return {
                "success": True,
                "text": result["text"],
                "session_id": str(state.session_id),
                "iterations": result["iterations"],
                "metadata": {
                    "skill_id": filter_result["skill_id"],
                    "reasoning": filter_result.get("reasoning", ""),
                    "tool_calls": result.get("tool_calls", []),
                    "loop_advisories": result.get("loop_advisories", []),
                    "trace_log_path": trace_log_file,
                }
            }

        except Exception as e:
            # 记录错误
            tracker.complete(error=str(e))

            return {
                "success": False,
                "error": str(e),
                "session_id": str(state.session_id)
            }

    def _build_messages(
        self,
        state: AgentState,
        skill_prompt: str,
        online_memories: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        构建消息历史（包含 system prompt + 线上记忆）

        Args:
            state: 会话状态
            skill_prompt: 技能 prompt
            online_memories: 线上记忆召回的记忆

        Returns:
            消息列表
        """
        # 构建 system prompt（包含线上记忆）
        system_prompt = self._build_system_prompt(skill_prompt, online_memories)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加对话历史
        for msg in state.conversation_history:
            message_dict = {
                "role": msg.role,
                "content": msg.content
            }

            # 保留 tool_calls（assistant 消息）
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls

            # 保留 tool_call_id（tool 消息）
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id

            messages.append(message_dict)

        return messages

    def _build_system_prompt(
        self,
        skill_prompt: str,
        online_memories: List[Dict[str, Any]] = None
    ) -> str:
        """
        动态构建 system prompt

        Args:
            skill_prompt: 技能 prompt
            online_memories: 线上记忆召回的记忆

        Returns:
            system prompt
        """
        from src.core.agent.prompts import build_agent_prompt

        # 将线上记忆转换为统一格式
        memories = []
        if online_memories:
            for mem in online_memories:
                memories.append({
                    "fact_text": mem["content"],
                    "source": mem.get("source", "online_memory")
                })

        return build_agent_prompt(skill_prompt, memories)

    async def _agent_loop(
        self,
        state: AgentState,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        Agent 主循环

        Args:
            state: 会话状态
            messages: 消息历史
            tools: 工具列表
            stream_callback: 流式输出回调

        Returns:
            执行结果
        """
        iteration = 0
        accumulated_text = ""
        all_tool_calls = []
        iteration_traces = []
        loop_advisories = []
        active_tools = tools
        tool_cache: Dict[str, Dict[str, Any]] = {}
        total_tool_calls = 0
        tool_signature_counts: Dict[str, int] = {}
        warned_signatures = set()

        while iteration < self.max_iterations:
            iteration += 1

            # 调用 LLM
            response = await self.llm_client.chat_completion(
                messages=messages,
                tools=active_tools,
                stream=False
            )

            # 检查响应是否有效
            if not response.choices or len(response.choices) == 0:
                debug_print(f"⚠️  LLM 返回空响应，终止循环")
                break

            # 提取响应内容
            content = response.choices[0].message.content or ""
            tool_calls = response.choices[0].message.tool_calls
            reasoning_content = ""
            if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
                reasoning_content = response.choices[0].message.reasoning_content

            iteration_trace = {
                "iteration": iteration,
                "assistant_plan": self._truncate_text(content, 1800),
                "reasoning": self._truncate_text(reasoning_content, 1800),
                "tool_calls": [],
                "advisories": [],
            }

            # 输出文本内容
            if content and stream_callback:
                stream_callback('text', content)
            accumulated_text += content

            # 如果没有工具调用，结束循环
            if not tool_calls:
                iteration_trace["summary"] = "no tool calls; finalize response"
                iteration_traces.append(iteration_trace)
                state.add_message("assistant", content)
                break

            # 处理工具调用
            tool_results, tool_exec_infos = await self._execute_tools(
                tool_calls=tool_calls,
                stream_callback=stream_callback,
                tool_cache=tool_cache,
            )

            # 收集工具调用信息
            for tool_call, result, exec_info in zip(tool_calls, tool_results, tool_exec_infos):
                try:
                    parsed_args = json.loads(tool_call.function.arguments)
                except Exception:
                    parsed_args = {"_raw_arguments": tool_call.function.arguments}
                signature = exec_info.get("signature")
                if signature:
                    tool_signature_counts[signature] = tool_signature_counts.get(signature, 0) + 1
                    repeat_count = tool_signature_counts[signature]
                    if repeat_count >= self.loop_review_repeat_threshold and signature not in warned_signatures:
                        warned_signatures.add(signature)
                        advisory = (
                            f"loop-review hint: `{tool_call.function.name}` with same args repeated {repeat_count} times; "
                            "double-check whether this is new evidence."
                        )
                        messages.append({
                            "role": "system",
                            "content": (
                                f"你已经多次重复调用 `{tool_call.function.name}` 且参数相同。"
                                "请自查是否真的有新增信息；如果没有，请停止重复调用并直接总结。"
                            ),
                        })
                        loop_advisories.append({
                            "iteration": iteration,
                            "type": "repeat_signature",
                            "message": advisory,
                            "tool": tool_call.function.name,
                            "signature": signature,
                            "repeat_count": repeat_count,
                        })
                        iteration_trace["advisories"].append(advisory)

                all_tool_calls.append({
                    "name": tool_call.function.name,
                    "args": parsed_args,
                    "result": result,
                    "cached": bool(exec_info.get("cached", False)),
                    "signature": signature,
                })
                iteration_trace["tool_calls"].append({
                    "name": tool_call.function.name,
                    "args": parsed_args,
                    "cached": bool(exec_info.get("cached", False)),
                    "signature": signature,
                    "result_summary": self._summarize_tool_result(tool_call.function.name, result),
                })

            # 添加助手消息到消息列表
            assistant_message = {
                "role": "assistant",
                "content": content if content else None,  # 空字符串转为 None
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            }

            # 如果响应包含 reasoning_content（Kimi k2.5），保留它
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content

            messages.append(assistant_message)

            # 添加工具结果消息
            for tool_call, result in zip(tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # 保存到会话状态
            state.add_message("assistant", content, tool_calls=tool_calls)

            # 保存 tool 结果消息
            for tool_call, result in zip(tool_calls, tool_results):
                state.add_message("tool", json.dumps(result, ensure_ascii=False), tool_call_id=tool_call.id)

            total_tool_calls += len(tool_calls)
            if total_tool_calls >= self.max_tool_calls_per_turn:
                advisory = (
                    f"soft budget warning: total tool calls reached {total_tool_calls} "
                    f"(configured max {self.max_tool_calls_per_turn})"
                )
                messages.append({
                    "role": "system",
                    "content": (
                        f"本轮工具调用已达到建议上限（{self.max_tool_calls_per_turn} 次）。"
                        "请优先基于已有信息给出结论。若必须继续调用工具，请先说明新增价值。"
                    ),
                })
                loop_advisories.append({
                    "iteration": iteration,
                    "type": "tool_budget_warning",
                    "message": advisory,
                    "total_tool_calls": total_tool_calls,
                })
                iteration_trace["advisories"].append(advisory)

            iteration_trace["summary"] = self._build_iteration_summary(iteration_trace["tool_calls"])
            iteration_traces.append(iteration_trace)

        if iteration >= self.max_iterations:
            messages.append({
                "role": "system",
                "content": (
                    f"你已达到最大迭代次数（{self.max_iterations}）。"
                    "请停止工具调用，直接给出基于已有证据的最终结论。"
                ),
            })
            try:
                final_response = await self.llm_client.chat_completion(
                    messages=messages,
                    tools=[],
                    stream=False,
                )
                if final_response.choices and len(final_response.choices) > 0:
                    final_content = final_response.choices[0].message.content or ""
                    if final_content:
                        if stream_callback:
                            stream_callback('text', final_content)
                        accumulated_text += final_content
                        state.add_message("assistant", final_content)
                        iteration_traces.append({
                            "iteration": iteration + 1,
                            "assistant_plan": self._truncate_text(final_content, 1800),
                            "reasoning": "",
                            "tool_calls": [],
                            "advisories": [
                                f"forced finalization after max iterations {self.max_iterations}"
                            ],
                            "summary": "forced final answer without tools",
                        })
            except Exception as e:
                loop_advisories.append({
                    "iteration": iteration,
                    "type": "finalization_error",
                    "message": f"failed to finalize after max iterations: {e}",
                })

        return {
            "text": accumulated_text,
            "iterations": iteration,
            "tool_calls": all_tool_calls,
            "iteration_traces": iteration_traces,
            "loop_advisories": loop_advisories,
        }

    async def _execute_tools(
        self,
        tool_calls: List[Any],
        stream_callback=None,
        tool_cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        执行工具调用

        Args:
            tool_calls: 工具调用列表
            stream_callback: 流式输出回调

        Returns:
            (工具执行结果列表, 执行元信息列表)
        """
        results = []
        execution_infos = []

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except Exception:
                results.append({
                    "success": False,
                    "error": f"工具参数解析失败: {tool_call.function.arguments}",
                })
                execution_infos.append({
                    "tool_name": function_name,
                    "args": {"_raw_arguments": tool_call.function.arguments},
                    "cached": False,
                    "signature": None,
                })
                continue
            signature = self._build_tool_signature(function_name, arguments)

            # 输出工具调用可视化
            if stream_callback:
                viz_text = self.tool_registry.format_visualization(
                    tool_name=function_name,
                    arguments=arguments,
                    stage="calling"
                )
                stream_callback('tool_call', viz_text + '\n')

            if tool_cache is not None and signature in tool_cache:
                result = copy.deepcopy(tool_cache[signature])
                cached = True
            else:
                # 执行工具
                result = await self.tool_registry.execute_tool(
                    tool_name=function_name,
                    db=self.db,
                    **arguments
                )
                result = self._sanitize_tool_result(function_name, result)
                if tool_cache is not None:
                    tool_cache[signature] = copy.deepcopy(result)
                cached = False

            # 输出工具结果可视化
            if stream_callback:
                if result.get("success"):
                    viz_text = self.tool_registry.format_visualization(
                        tool_name=function_name,
                        arguments={**arguments, **result.get("data", {})},
                        stage="success"
                    )
                else:
                    viz_text = self.tool_registry.format_visualization(
                        tool_name=function_name,
                        arguments={**arguments, "error": result.get("error", "")},
                        stage="error"
                    )
                stream_callback('tool_result', viz_text + '\n\n')

            results.append(result)
            execution_infos.append({
                "tool_name": function_name,
                "args": arguments,
                "cached": cached,
                "signature": signature,
            })

        return results, execution_infos

    def _build_tool_signature(self, function_name: str, arguments: Dict[str, Any]) -> str:
        canonical_arguments = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        return f"{function_name}:{canonical_arguments}"

    def _normalize_tool_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize tool result envelopes to a single `{success, data|error}` shape.

        Some legacy tools already return a wrapped structure and may get wrapped again
        by the registry (`{"success": true, "data": {"success": ..., "data": ...}}`).
        """
        if not isinstance(result, dict):
            return {"success": False, "error": "invalid tool result"}

        normalized = dict(result)
        data = normalized.get("data")

        # Unwrap nested standard envelope.
        if isinstance(data, dict) and "success" in data and ("data" in data or "error" in data):
            outer_success = bool(normalized.get("success", True))
            inner_success = bool(data.get("success"))
            normalized["success"] = outer_success and inner_success
            if "data" in data:
                normalized["data"] = data.get("data")
            else:
                normalized.pop("data", None)
            if data.get("error"):
                normalized["error"] = data.get("error")
            return normalized

        # Handle legacy wrapped error payload: {"success": true, "data": {"error": "..."}}
        if (
            isinstance(data, dict)
            and isinstance(data.get("error"), str)
            and len(data) == 1
            and bool(normalized.get("success", True))
        ):
            normalized["success"] = False
            normalized["error"] = data["error"]
            normalized.pop("data", None)

        return normalized

    def _truncate_text(self, text: str, max_chars: int = 1600) -> str:
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"...(truncated {len(text) - max_chars} chars)"

    def _summarize_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_tool_result(result)
        summary: Dict[str, Any] = {
            "success": bool(normalized.get("success")),
            "highlights": [],
            "image_paths": [],
        }
        if normalized.get("error"):
            summary["error"] = self._truncate_text(str(normalized.get("error")), 400)
            return summary

        data = normalized.get("data")
        if not isinstance(data, dict):
            return summary

        image_path = data.get("image_path")
        if isinstance(image_path, str) and image_path:
            summary["image_paths"].append(image_path)
            summary["highlights"].append(f"image: {image_path}")
        thumbnail_path = data.get("thumbnail")
        if isinstance(thumbnail_path, str) and thumbnail_path:
            summary["image_paths"].append(thumbnail_path)
            summary["highlights"].append(f"thumbnail: {thumbnail_path}")

        if tool_name == "get_cad_metadata":
            bounds = data.get("bounds") or {}
            if isinstance(bounds, dict) and bounds.get("width") and bounds.get("height"):
                summary["highlights"].append(
                    f"bounds: ({bounds.get('min_x')}, {bounds.get('min_y')}) + {bounds.get('width')}x{bounds.get('height')}"
                )
            if isinstance(data.get("entity_count"), int):
                summary["highlights"].append(f"entities: {data.get('entity_count')}")
            if isinstance(data.get("layer_count"), int):
                summary["highlights"].append(f"layers: {data.get('layer_count')}")

        if tool_name == "inspect_region":
            region_info = data.get("region_info") or {}
            if isinstance(region_info, dict):
                bbox = region_info.get("bbox") or {}
                if isinstance(bbox, dict) and bbox.get("width") and bbox.get("height"):
                    summary["highlights"].append(
                        f"bbox: ({bbox.get('x')}, {bbox.get('y')}) + {bbox.get('width')}x{bbox.get('height')}"
                    )
            entity_summary = data.get("entity_summary") or {}
            if isinstance(entity_summary, dict):
                total = entity_summary.get("total_count")
                if isinstance(total, int):
                    summary["highlights"].append(f"entity_total: {total}")
            key_content = data.get("key_content") or {}
            if isinstance(key_content, dict):
                text_count = key_content.get("text_count")
                if isinstance(text_count, int):
                    summary["highlights"].append(f"text_count: {text_count}")

        if tool_name == "extract_cad_entities":
            total = data.get("total_count")
            if isinstance(total, int):
                summary["highlights"].append(f"total_count: {total}")
            entity_count = data.get("entity_count")
            if isinstance(entity_count, dict) and entity_count:
                keys = ",".join(list(entity_count.keys())[:6])
                summary["highlights"].append(f"types: {keys}")

        if tool_name in ("write_file", "append_to_file", "read_file", "list_files"):
            for key in ("filename", "file_path", "line_count", "total_count"):
                if key in data:
                    summary["highlights"].append(f"{key}: {data[key]}")

        return summary

    def _build_iteration_summary(self, tool_entries: List[Dict[str, Any]]) -> str:
        if not tool_entries:
            return "no tool action"
        highlights = []
        for item in tool_entries:
            name = item.get("name")
            success = item.get("result_summary", {}).get("success")
            cached = item.get("cached")
            marker = "ok" if success else "err"
            cache_tag = ",cached" if cached else ""
            highlights.append(f"{name}({marker}{cache_tag})")
        return " -> ".join(highlights)

    def _to_workspace_markdown_path(self, path_str: str) -> str:
        if not path_str:
            return ""
        path = str(path_str).replace("\\", "/")
        if path.startswith("./"):
            return path
        workspace_marker = "workspace/"
        marker_idx = path.find(workspace_marker)
        if marker_idx >= 0:
            return "./" + path[marker_idx + len(workspace_marker):]
        return path

    def _append_detailed_trace_log(
        self,
        session_id: str,
        user_message: str,
        skill_id: Optional[str],
        loop_result: Dict[str, Any],
    ) -> Optional[str]:
        """
        Write a detailed markdown trace log for each turn.
        """
        try:
            log_path = self.trace_log_path
            log_path.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines: List[str] = []
            lines.append(f"## {timestamp} | session `{session_id[:8]}` | skill `{skill_id or 'auto'}`")
            lines.append("")
            lines.append("### User Prompt")
            lines.append(self._truncate_text(user_message, 2000))
            lines.append("")

            advisories = loop_result.get("loop_advisories", [])
            if advisories:
                lines.append("### Loop Review Hints")
                for item in advisories:
                    lines.append(f"- [iter {item.get('iteration')}] {item.get('message')}")
                lines.append("")

            lines.append("### Iteration Trace")
            iteration_traces = loop_result.get("iteration_traces", [])
            if not iteration_traces:
                lines.append("- (no trace captured)")
                lines.append("")
            else:
                for iter_item in iteration_traces:
                    iter_no = iter_item.get("iteration")
                    lines.append(f"#### Iteration {iter_no}")
                    plan = iter_item.get("assistant_plan") or ""
                    reasoning = iter_item.get("reasoning") or ""
                    if plan:
                        lines.append("Plan / Thought:")
                        lines.append(self._truncate_text(plan, 1800))
                        lines.append("")
                    if reasoning:
                        lines.append("Reasoning:")
                        lines.append(self._truncate_text(reasoning, 1800))
                        lines.append("")

                    iter_adv = iter_item.get("advisories") or []
                    if iter_adv:
                        lines.append("Advisories:")
                        for msg in iter_adv:
                            lines.append(f"- {msg}")
                        lines.append("")

                    tool_entries = iter_item.get("tool_calls") or []
                    if tool_entries:
                        lines.append("Tool Calls:")
                        for idx, entry in enumerate(tool_entries, 1):
                            lines.append(f"{idx}. `{entry.get('name')}`")
                            lines.append(f"- cached: `{entry.get('cached')}`")
                            arg_str = json.dumps(entry.get("args", {}), ensure_ascii=False)
                            lines.append(f"- args: `{self._truncate_text(arg_str, 800)}`")
                            summary = entry.get("result_summary") or {}
                            lines.append(f"- success: `{summary.get('success')}`")
                            if summary.get("error"):
                                lines.append(f"- error: `{summary.get('error')}`")
                            for hl in summary.get("highlights", []):
                                lines.append(f"- {hl}")
                            for image_path in summary.get("image_paths", []):
                                md_path = self._to_workspace_markdown_path(image_path)
                                lines.append(f"- image_path: `{image_path}`")
                                lines.append(f"![iter{iter_no}-tool{idx}]({md_path})")
                            lines.append("")
                    lines.append(f"Progress: {iter_item.get('summary', '')}")
                    lines.append("")

            lines.append("### Final Answer")
            lines.append(self._truncate_text(loop_result.get("text", ""), 3000))
            lines.append("")
            lines.append("---")
            lines.append("")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))

            return str(log_path)
        except Exception as e:
            debug_print(f"⚠️ 自动详细工作日志写入失败: {e}")
            return None

    def _sanitize_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trim oversized tool payloads before they are appended into chat history.
        """
        safe = self._normalize_tool_result(result)
        data = safe.get("data")
        if isinstance(data, dict):
            safe_data = dict(data)

            image_base64 = safe_data.get("image_base64")
            if isinstance(image_base64, str) and image_base64:
                safe_data.pop("image_base64", None)
                safe_data["image_base64_omitted"] = True
                safe_data["image_base64_chars"] = len(image_base64)

            key_content = safe_data.get("key_content")
            if isinstance(key_content, dict):
                texts = key_content.get("texts")
                if isinstance(texts, list) and len(texts) > 20:
                    safe_key_content = dict(key_content)
                    safe_key_content["texts"] = texts[:20]
                    safe_key_content["texts_truncated"] = len(texts) - 20
                    safe_data["key_content"] = safe_key_content

            safe["data"] = safe_data

        try:
            serialized = json.dumps(safe, ensure_ascii=False)
        except Exception:
            return {
                "success": bool(result.get("success")),
                "error": result.get("error", f"工具 {tool_name} 结果序列化失败"),
            }

        if len(serialized) <= self.max_tool_result_chars:
            return safe

        compact_data = {}
        if isinstance(safe.get("data"), dict):
            src = safe["data"]
            for key in (
                "image_path",
                "thumbnail",
                "region_info",
                "entity_summary",
                "key_content",
                "bounds",
                "filename",
                "entity_count",
                "total_count",
                "layer_count",
                "image_base64_omitted",
                "image_base64_chars",
            ):
                if key in src:
                    compact_data[key] = src[key]

        compact = {
            "success": bool(safe.get("success")),
            "_truncated": True,
            "_original_chars": len(serialized),
        }
        if "error" in safe:
            compact["error"] = safe.get("error")
        if compact_data:
            compact["data"] = compact_data

        compact_serialized = json.dumps(compact, ensure_ascii=False)
        if len(compact_serialized) <= self.max_tool_result_chars:
            return compact

        minimal = {
            "success": bool(safe.get("success")),
            "_truncated": True,
            "_original_chars": len(serialized),
            "data": {
                "note": f"tool result omitted due to size: {len(serialized)} chars",
            },
        }
        if isinstance(safe.get("data"), dict) and safe["data"].get("image_path"):
            minimal["data"]["image_path"] = safe["data"]["image_path"]
        if "error" in safe:
            minimal["error"] = safe.get("error")
        return minimal
