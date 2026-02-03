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

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.agent.state import AgentState, get_session_manager
from src.infrastructure.llm.deepseek_client import DeepSeekClient
from src.core.memory.embedding_service import EmbeddingService
from src.core.memory.online_memory_adapter import OnlineMemoryAdapter
from src.core.skills.skill_service import SkillService
from src.core.skills.filter_service import FilterService
from src.core.skills.tool_registry import get_tool_registry
from src.core.utils.performance_tracker import PerformanceTracker
from src.core.utils.debug import debug_print


class MemoryDrivenAgent:
    """记忆驱动的统一 Agent"""

    def __init__(self, db: AsyncSession, use_reasoner: bool = False):
        """
        初始化 Agent

        Args:
            db: 数据库会话
            use_reasoner: 是否使用 reasoner 模式
        """
        self.db = db
        self.llm_client = DeepSeekClient(use_reasoner=use_reasoner)
        self.session_manager = get_session_manager()
        self.max_iterations = 20

        # 服务层
        self.embedding_service = EmbeddingService()
        self.skill_service = SkillService(db)
        self.filter_service = FilterService()

        # 线上记忆适配器
        self.online_memory_adapter = OnlineMemoryAdapter(enabled=True)

        # 工具注册表
        self.tool_registry = get_tool_registry()

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

            # 2. 检索 skills
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
            if filter_result["skill_id"]:
                skill = await self.skill_service.get_skill_by_id(filter_result["skill_id"])
                if skill:
                    tools = self.tool_registry.get_tools_by_names(skill.tool_set)
                    skill_prompt = skill.prompt_template

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
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

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

        # 将线上记忆转换为 facts 格式
        all_facts = []
        if online_memories:
            for mem in online_memories:
                all_facts.append({
                    "fact_text": mem["content"],
                    "source": mem.get("source", "online_memory")
                })

        return build_agent_prompt(skill_prompt, all_facts)

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

        while iteration < self.max_iterations:
            iteration += 1

            # 调用 LLM
            response = await self.llm_client.chat_completion(
                messages=messages,
                tools=tools,
                stream=False
            )

            # 检查响应是否有效
            if not response.choices or len(response.choices) == 0:
                debug_print(f"⚠️  LLM 返回空响应，终止循环")
                break

            # 提取响应内容
            content = response.choices[0].message.content or ""
            tool_calls = response.choices[0].message.tool_calls

            # 输出文本内容
            if content and stream_callback:
                stream_callback('text', content)
            accumulated_text += content

            # 如果没有工具调用，结束循环
            if not tool_calls:
                state.add_message("assistant", content)
                break

            # 处理工具调用
            tool_results = await self._execute_tools(
                tool_calls=tool_calls,
                stream_callback=stream_callback
            )

            # 收集工具调用信息
            for tool_call, result in zip(tool_calls, tool_results):
                all_tool_calls.append({
                    "name": tool_call.function.name,
                    "args": json.loads(tool_call.function.arguments),
                    "result": result
                })

            # 添加助手消息到消息列表
            messages.append({
                "role": "assistant",
                "content": content,
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
            })

            # 添加工具结果消息
            for tool_call, result in zip(tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # 保存到会话状态
            state.add_message("assistant", content, tool_calls=tool_calls)

        return {
            "text": accumulated_text,
            "iterations": iteration,
            "tool_calls": all_tool_calls
        }

    async def _execute_tools(
        self,
        tool_calls: List[Any],
        stream_callback=None
    ) -> List[Dict[str, Any]]:
        """
        执行工具调用

        Args:
            tool_calls: 工具调用列表
            stream_callback: 流式输出回调

        Returns:
            工具执行结果列表
        """
        results = []

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # 输出工具调用可视化
            if stream_callback:
                viz_text = self.tool_registry.format_visualization(
                    tool_name=function_name,
                    arguments=arguments,
                    stage="calling"
                )
                stream_callback('tool_call', viz_text + '\n')

            # 执行工具
            result = await self.tool_registry.execute_tool(
                tool_name=function_name,
                db=self.db,
                **arguments
            )

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

        return results

