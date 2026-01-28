"""
ReAct Agent core - DeepSeek Reasoner with function calling.

Architecture:
    User Query
        ↓
    Reasoner Model (thinking mode)
        ↓
    Reasoning → Action (tool call) → Observation
        ↓ (loop until no more actions)
    Final Answer
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from uuid import UUID
import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.state import AgentState, get_session_manager
from src.agent.tools_simplified import get_tool_schemas, execute_tool, format_tool_visualization
from src.llm.deepseek_client import DeepSeekClient
from src.agent.prompts import GENERAL_AGENT_PROMPT


class ReActAgent:
    """
    ReAct Agent using DeepSeek Reasoner with function calling.

    The reasoner model thinks, decides actions, and continues reasoning
    until it provides a final answer.
    """

    def __init__(self, db: AsyncSession, use_reasoner: bool = True):
        self.db = db
        self.llm_client = DeepSeekClient(use_reasoner=use_reasoner)
        self.session_manager = get_session_manager()
        self.max_iterations = 20  # Support batch operations like deleting multiple tasks

    async def process_message(
        self,
        user_message: str,
        session_id: Optional[UUID] = None,
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        Process user message using DeepSeek Reasoner.

        Args:
            user_message: User's message
            session_id: Optional session ID
            stream_callback: Optional callback for streaming (thinking, content)

        Returns:
            Agent response with text and metadata
        """
        # Get or create session
        if session_id:
            state = self.session_manager.get_session(session_id)
            if not state:
                state = self.session_manager.create_session()
        else:
            state = self.session_manager.create_session()

        # Add user message to history
        state.add_message("user", user_message)

        try:
            # Build conversation history
            messages = self._build_messages(state)
            tools = get_tool_schemas()

            # ReAct loop: Reasoner thinks → acts → observes → continues
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1

                # Call reasoner model
                # Note: We'll enable streaming only for final answer (no tool calls)
                response = await self.llm_client.chat_completion(
                    messages=messages,
                    tools=tools,
                    temperature=0.7,
                    stream=True
                )

                # Collect streaming response
                reasoning_content = ""
                content = ""
                tool_calls = []
                tool_calls_started = False

                async for chunk in response:
                    choice = chunk.choices[0] if chunk.choices else None
                    if not choice:
                        continue

                    delta = choice.delta

                    # Stream reasoning (thinking process)
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning_content += delta.reasoning_content
                        if stream_callback:
                            stream_callback('thinking', delta.reasoning_content)

                    # Collect content (don't stream yet - wait to see if there are tool calls)
                    if hasattr(delta, 'content') and delta.content:
                        content += delta.content

                    # Collect tool calls
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        tool_calls_started = True
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

                # Check if model wants to call tools
                if tool_calls:
                    # Output content (brief response)
                    if content and stream_callback:
                        stream_callback('content', content + '\n\n')

                    # Execute tools with visualization
                    tool_results = await self._execute_tool_calls_from_dict(
                        tool_calls,
                        stream_callback=stream_callback
                    )

                    # CRITICAL: Add assistant message with reasoning_content
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": reasoning_content,
                        "tool_calls": tool_calls
                    })

                    # Add tool results
                    for tc, result in zip(tool_calls, tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False)
                        })

                    # Continue loop
                    continue

                else:
                    # No more tool calls - final answer with pseudo-streaming
                    if content and stream_callback:
                        import time
                        for char in content:
                            stream_callback('content', char)
                            time.sleep(0.001)

                    final_response = content or "抱歉，我无法处理这个请求。"
                    state.add_message("assistant", final_response)

                    return {
                        "success": True,
                        "text": final_response,
                        "session_id": str(state.session_id),
                        "iterations": iteration,
                        "reasoning": reasoning_content
                    }

            # Max iterations reached
            return {
                "success": False,
                "text": "抱歉，处理超时了。请重新表述你的问题。",
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
        """
        Build message history for LLM.

        Args:
            state: Agent state with conversation history

        Returns:
            List of messages in OpenAI format
        """
        messages = [
            {"role": "system", "content": GENERAL_AGENT_PROMPT}
        ]

        # Add recent conversation history (last 10 messages)
        recent_messages = state.get_recent_messages(limit=10)
        for msg in recent_messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages

    async def _execute_tool_calls_from_dict(
        self,
        tool_calls: List[Dict[str, Any]],
        stream_callback=None
    ) -> List[Dict[str, Any]]:
        """Execute tool calls and output visualization."""
        results = []

        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]

            # Parse arguments
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                results.append({"error": f"Invalid JSON arguments: {arguments_str}"})
                continue

            # Send "calling" visualization
            if stream_callback:
                calling_text = format_tool_visualization(function_name, arguments, stage="calling")
                stream_callback('tool_call', calling_text)

            # Execute tool
            try:
                result = await execute_tool(function_name, self.db, **arguments)

                # Send result visualization
                if stream_callback:
                    if result.get("success"):
                        viz_data = {**arguments, **result.get("data", {})}
                        success_text = format_tool_visualization(function_name, viz_data, stage="success")
                        stream_callback('tool_result', success_text + '\n\n')
                    else:
                        error_data = {**arguments, "error": result.get("error", "Unknown error")}
                        error_text = format_tool_visualization(function_name, error_data, stage="error")
                        stream_callback('tool_result', error_text + '\n\n')

                results.append(result)
            except Exception as e:
                error_result = {"error": f"Tool execution failed: {str(e)}"}
                if stream_callback:
                    error_data = {**arguments, "error": str(e)}
                    error_text = format_tool_visualization(function_name, error_data, stage="error")
                    stream_callback('tool_result', error_text + '\n\n')
                results.append(error_result)

        return results
