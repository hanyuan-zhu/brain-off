"""
线上记忆接口适配器 - 替换 GauzMem

功能：
1. 调用线上 API 召回记忆 (search/bundle)
2. 异步存储对话到线上 API (memories/message)
3. 不影响现有的本地记忆系统
"""
from typing import List, Dict, Any, Optional
import os
import asyncio
import aiohttp
from pathlib import Path
from dotenv import load_dotenv

# 加载独立配置文件
env_path = Path(__file__).parent.parent.parent.parent / ".env.gauz"
if env_path.exists():
    load_dotenv(env_path)


class OnlineMemoryAdapter:
    """线上记忆 API 适配器"""

    def __init__(self, enabled: bool = True):
        """
        初始化适配器

        Args:
            enabled: 是否启用线上记忆（默认启用）
        """
        self.enabled = enabled
        self.base_url = os.getenv("ONLINE_MEMORY_API_URL", "http://43.139.19.144:1235/api/v1")
        self.project_id = os.getenv("ONLINE_MEMORY_PROJECT_ID", "chatbot")
        self.api_key = os.getenv("ONLINE_MEMORY_API_KEY", "")  # 如果需要认证

        # 确保 base_url 不以 / 结尾
        self.base_url = self.base_url.rstrip("/")

        if self.enabled:
            print(f"✅ 线上记忆适配器已启用 (URL: {self.base_url})")

    async def recall_memories(
        self,
        query: str,
        top_k: int = 5,
        enable_graph: bool = False,
        max_hops: int = 1
    ) -> List[Dict[str, Any]]:
        """
        从线上 API 召回相关记忆 (search/bundle)

        Args:
            query: 查询文本
            top_k: 返回记忆数量
            enable_graph: 是否启用图扩展
            max_hops: 最大跳数（1-3）

        Returns:
            记忆列表，格式：[{"content": "...", "source": "online_memory"}]
        """
        if not self.enabled:
            return []

        import time
        overall_start = time.time()

        try:
            print(f"🔍 [OnlineMemory] 开始召回记忆 (query={query[:50]}..., top_k={top_k})")

            # 构建请求体
            request_body = {
                "project_id": self.project_id,
                "query": query,
                "top_k": top_k
            }

            # 如果启用图扩展
            if enable_graph:
                request_body["expansions"] = {
                    "graph": {
                        "enabled": True,
                        "max_hops": max_hops
                    }
                }

            # 发送请求
            api_start = time.time()
            url = f"{self.base_url}/memories/search/bundle"

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"⚠️ API 返回错误: {response.status} - {error_text}")
                        return []

                    data = await response.json()

            api_duration = time.time() - api_start
            print(f"  ⏱️  API 调用耗时: {api_duration:.2f}s")

            # 解析响应
            convert_start = time.time()
            result = self._parse_bundle_response(data)
            convert_duration = time.time() - convert_start
            print(f"  ⏱️  数据转换耗时: {convert_duration:.3f}s")

            overall_duration = time.time() - overall_start
            print(f"✅ 线上记忆召回 {len(result)} 条记忆 (总耗时: {overall_duration:.2f}s)")

            # 性能警告
            if api_duration > 10:
                print(f"⚠️  [性能警告] API 调用耗时过长: {api_duration:.2f}s")

            return result

        except asyncio.TimeoutError:
            overall_duration = time.time() - overall_start
            print(f"⏳ 线上记忆召回超时 - 耗时: {overall_duration:.2f}s")
            return []
        except Exception as e:
            overall_duration = time.time() - overall_start
            print(f"⚠️ 线上记忆召回失败: {e} - 耗时: {overall_duration:.2f}s")
            return []

    def _parse_bundle_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析 bundle 搜索响应

        Args:
            data: API 响应数据

        Returns:
            统一格式的记忆列表
        """
        result = []

        # 1. 处理短期记忆 (short_term_memory)
        if data.get("short_term_memory"):
            stm = data["short_term_memory"]
            if stm.get("conversations"):
                for conv in stm["conversations"]:
                    result.append({
                        "content": conv.get("text", ""),
                        "source": "online_memory_short_term",
                        "type": "conversation",
                        "metadata": {
                            "chunk_id": conv.get("chunk_id"),
                            "speaker": conv.get("speaker"),
                            "indexed": False
                        }
                    })

        # 2. 处理长期记忆 bundles
        if data.get("bundles"):
            for bundle in data["bundles"]:
                # 处理 facts
                if bundle.get("facts"):
                    for fact in bundle["facts"]:
                        result.append({
                            "content": fact.get("fact_text", ""),
                            "source": "online_memory_fact",
                            "type": "fact",
                            "metadata": {
                                "fact_id": fact.get("fact_id"),
                                "bundle_id": bundle.get("bundle_id")
                            }
                        })

                # 处理 conversations
                if bundle.get("conversations"):
                    for conv in bundle["conversations"]:
                        result.append({
                            "content": conv.get("text", ""),
                            "source": "online_memory_conversation",
                            "type": "conversation",
                            "metadata": {
                                "chunk_id": conv.get("chunk_id"),
                                "speaker": conv.get("speaker"),
                                "bundle_id": bundle.get("bundle_id"),
                                "indexed": True
                            }
                        })

                # 处理 topics
                if bundle.get("topics"):
                    for topic in bundle["topics"]:
                        result.append({
                            "content": topic.get("summary", ""),
                            "source": "online_memory_topic",
                            "type": "topic",
                            "metadata": {
                                "topic_id": topic.get("topic_id"),
                                "bundle_id": bundle.get("bundle_id")
                            }
                        })

        return result

    async def store_message(
        self,
        text: str,
        user_id: str,
        session_id: str,
        role: str = "user",
        async_mode: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        存储消息到线上 API (memories/message)

        Args:
            text: 消息内容
            user_id: 用户 ID
            session_id: 会话 ID (run_id)
            role: 角色（user/assistant）
            async_mode: 是否异步模式

        Returns:
            响应数据或 None（如果失败）
        """
        if not self.enabled:
            return None

        try:
            # 映射 role 到 speaker
            speaker = "user" if role == "user" else "agent"

            # 构建请求体
            request_body = {
                "project_id": self.project_id,
                "message": {
                    "text": text,
                    "user_id": user_id,
                    "run_id": session_id,
                    "speaker": speaker
                },
                "async_mode": async_mode
            }

            # 发送请求（注意：端点是 /memories/messages 复数形式）
            url = f"{self.base_url}/memories/messages"

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"⚠️ 存储消息失败: {response.status} - {error_text}")
                        return None

                    data = await response.json()

            print(f"✅ 线上记忆存储消息: chunk_id={data.get('chunk_id')}, task_id={data.get('task_id')}")
            return data

        except asyncio.TimeoutError:
            print(f"⏳ 线上记忆存储超时（后台处理中）")
            return {"status": "timeout"}
        except Exception as e:
            print(f"⚠️ 线上记忆存储失败: {e}")
            return None
