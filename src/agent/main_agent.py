"""
Main Agent - 顶层路由 Agent

职责：
1. 处理通用对话（问候、闲聊、解释）
2. 识别任务管理意图
3. 调用 task_agent 工具处理任务管理
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.state import AgentState, get_session_manager
from src.llm.deepseek_client import DeepSeekClient
from src.agent.prompts import MAIN_AGENT_PROMPT


def get_main_agent_tools() -> List[Dict[str, Any]]:
    """获取 Main Agent 的工具列表"""
    from src.agent.task_agent_tool import TASK_AGENT_SCHEMA
    return [TASK_AGENT_SCHEMA]


class MainAgent:
    """
    Main Agent - 顶层路由 Agent

    接口与 ReActAgent 完全一致，确保可以无缝替换
    """

    def __init__(self, db: AsyncSession, use_reasoner: bool = False):
        self.db = db
        # Main Agent 使用 chat 模式（快速响应，不需要显示思考过程）
        self.llm_client = DeepSeekClient(use_reasoner=False)
        self.session_manager = get_session_manager()
        self.max_iterations = 5  # Main Agent 迭代次数少

    async def process_message(
        self,
        user_message: str,
        session_id: Optional[UUID] = None,
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        处理用户消息

        接口与 ReActAgent 完全一致，确保无缝替换
        """
        # 获取或创建会话
        if session_id:
            state = self.session_manager.get_session(session_id)
            if not state:
                state = self.session_manager.create_session()
        else:
            state = self.session_manager.create_session()

        # 添加用户消息
        state.add_message("user", user_message)

        try:
            # 构建消息历史
            messages = self._build_messages(state)
            tools = get_main_agent_tools()

            # ReAct 循环
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1

                # 调用 LLM
                response = await self.llm_client.chat_completion(
                    messages=messages,
                    tools=tools,
                    temperature=0.7,
                    stream=True
                )

                # 收集流式响应
                content = ""
                tool_calls = []

                async for chunk in response:
                    choice = chunk.choices[0] if chunk.choices else None
                    if not choice:
                        continue

                    delta = choice.delta

                    # 收集内容
                    if hasattr(delta, 'content') and delta.content:
                        content += delta.content
                        if stream_callback:
                            stream_callback('content', delta.content)

                    # 收集工具调用
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tc in delta.tool_calls:
                            if len(tool_calls) <= tc.index:
                                tool_calls.append({
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })
                            if tc.function.name:
                                tool_calls[tc.index]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments

                # 检查是否调用工具
                if tool_calls:
                    # 输出换行
                    if stream_callback:
                        stream_callback('content', '\n\n')

                    # 执行工具（关键：透传 stream_callback）
                    tool_results = await self._execute_tool_calls(
                        tool_calls,
                        session_id=state.session_id,
                        stream_callback=stream_callback
                    )

                    # 检查是否有 skill 类型的工具
                    has_skill = any(r.get("tool_type") == "skill" for r in tool_results)
                    all_success = all(r.get("success", False) for r in tool_results)

                    if has_skill and all_success:
                        # Skill 已回复，Main Agent 保持沉默
                        # 不记录 tool_calls，只记录引导语（如果有）
                        if content.strip():
                            state.add_message("assistant", content)

                        return {
                            "success": True,
                            "text": content,
                            "session_id": str(state.session_id),
                            "iterations": iteration
                        }

                    # 纯 Tool 类型或失败：正常记录 tool_calls
                    # 添加到消息历史
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    })

                    for tc, result in zip(tool_calls, tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False)
                        })

                    continue

                else:
                    # 最终回复
                    final_response = content or "抱歉，我无法处理这个请求。"
                    state.add_message("assistant", final_response)

                    return {
                        "success": True,
                        "text": final_response,
                        "session_id": str(state.session_id),
                        "iterations": iteration
                    }

            # 超时
            return {
                "success": False,
                "text": "抱歉，处理超时了。",
                "session_id": str(state.session_id),
                "error": "Max iterations reached"
            }

        except Exception as e:
            error_msg = f"处理消息时出错：{str(e)}"
            state.add_message("assistant", error_msg)
            return {
                "success": False,
                "text": error_msg,
                "session_id": str(state.session_id),
                "error": str(e)
            }

    def _build_messages(self, state: AgentState) -> List[Dict[str, Any]]:
        """构建消息历史"""
        messages = [
            {"role": "system", "content": MAIN_AGENT_PROMPT}
        ]

        # 获取最近 10 条消息
        recent_messages = state.get_recent_messages(limit=10)
        for msg in recent_messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages

    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        session_id: UUID,
        stream_callback=None
    ) -> List[Dict[str, Any]]:
        """执行工具调用"""
        from src.agent.task_agent_tool import (
            task_agent_tool,
            format_task_agent_visualization
        )

        results = []

        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]

            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                results.append({"error": f"Invalid JSON: {arguments_str}"})
                continue

            # 发送调用可视化
            if stream_callback:
                calling_text = format_task_agent_visualization("calling")
                stream_callback('tool_call', calling_text)

            # 执行工具
            if function_name == "todos":
                try:
                    result = await task_agent_tool(
                        db=self.db,
                        user_request=arguments["user_request"],
                        session_id=session_id,
                        stream_callback=stream_callback,  # 关键：透传
                        use_reasoner=False  # 改为 Chat 模式，快速响应
                    )

                    # 发送结果可视化
                    if stream_callback:
                        if result.get("success"):
                            success_text = format_task_agent_visualization("success")
                            stream_callback('tool_result', success_text + '\n\n')
                        else:
                            error_text = format_task_agent_visualization(
                                "error",
                                error=result.get("error", "Unknown error")
                            )
                            stream_callback('tool_result', error_text + '\n\n')

                    results.append(result)
                except Exception as e:
                    error_result = {"error": str(e)}
                    if stream_callback:
                        error_text = format_task_agent_visualization("error", error=str(e))
                        stream_callback('tool_result', error_text + '\n\n')
                    results.append(error_result)
            else:
                results.append({"error": f"Unknown tool: {function_name}"})

        return results
