"""
DeepSeek API client for LLM interactions.
"""
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.config import settings


class DeepSeekClient:
    """Client for interacting with DeepSeek API."""

    def __init__(self, use_reasoner: bool = True):
        """Initialize DeepSeek client using OpenAI-compatible API."""
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )
        # Use reasoner model to see thinking process
        self.model = "deepseek-reasoner" if use_reasoner else "deepseek-chat"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False
    ):
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tools: List of tool definitions for function calling
            tool_choice: Tool choice strategy ('auto', 'none', or specific tool)
            stream: Whether to stream the response

        Returns:
            Response dict from the API (or async generator if stream=True)
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        response = await self.client.chat.completions.create(**kwargs)
        return response

    async def simple_chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Simple chat without function calling.

        Args:
            user_message: User's message
            system_prompt: Optional system prompt
            temperature: Sampling temperature

        Returns:
            AI's response text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await self.chat_completion(messages, temperature=temperature)
        return response.choices[0].message.content
