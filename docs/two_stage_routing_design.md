# 两阶段路由架构设计

## 核心思想

**打破 Function Calling 的限制，用纯 LLM 做意图分类**

```
用户输入
    ↓
阶段 1：意图分类（Main Agent，无 tools）
    ├─ 输出: "chat" → 阶段 2a：直接对话
    └─ 输出: "todos" → 阶段 2b：调用 Task Agent Skill
```

---

## 阶段 1：意图分类

### Prompt 设计

```python
INTENT_CLASSIFIER_PROMPT = """判断用户输入的意图类型。

意图类型：
- chat: 日常对话、问候、闲聊、知识问答、感谢等
- todos: 任务管理（创建、查看、更新、删除任务）

只输出意图类型（chat 或 todos），不要解释。"""
```

### 实现

```python
async def classify_intent(user_input: str) -> str:
    """
    分类用户意图

    Returns:
        "chat" 或 "todos"
    """
    response = await llm_client.chat_completion(
        messages=[
            {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
            {"role": "user", "content": user_input}
        ],
        temperature=0.0,  # 确定性输出
        max_tokens=10,    # 只需要一个词
        stream=False
    )

    intent = response.strip().lower()

    # 容错处理
    if "todos" in intent or "task" in intent:
        return "todos"
    else:
        return "chat"
```

### 特点

- **极简 Prompt**：只有 3 行说明
- **无 Tool 噪音**：完全没有 function calling JSON
- **快速**：max_tokens=10，几乎瞬间返回
- **准确**：意图分类是 LLM 的强项

---

## 阶段 2a：Chat 模式

### Prompt 设计

```python
CHAT_AGENT_PROMPT = """你是一个友好的 AI 助手。

输出纯文本，不要使用 Markdown 格式。"""
```

### 实现

```python
async def chat_response(user_input: str, history: List) -> str:
    """
    处理日常对话
    """
    messages = [
        {"role": "system", "content": CHAT_AGENT_PROMPT},
        *history,
        {"role": "user", "content": user_input}
    ]

    response = await llm_client.chat_completion(
        messages=messages,
        temperature=0.7,
        stream=True
    )

    return response
```

### 特点

- **完全泛化**：没有任何任务管理相关的噪音
- **自然对话**：LLM 本身的能力
- **极简 Prompt**：只说输出格式

---

## 阶段 2b：Todos 模式

### 实现

```python
async def todos_response(user_input: str, session_id: UUID, stream_callback) -> Dict:
    """
    调用 Task Agent Skill
    """
    # 显示切换可视化
    if stream_callback:
        stream_callback('tool_call', '【切换到任务管理模式】\n')

    # 调用 Task Agent
    result = await task_agent.process_message(
        user_message=user_input,
        session_id=session_id,
        stream_callback=stream_callback
    )

    # 显示完成可视化
    if stream_callback:
        stream_callback('tool_result', '\n【任务管理完成】\n\n')

    return result
```

---

## 完整流程

### Main Agent 实现

```python
class MainAgent:
    """
    两阶段路由 Main Agent
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = DeepSeekClient(use_reasoner=False)
        self.session_manager = get_session_manager()

    async def process_message(
        self,
        user_message: str,
        session_id: Optional[UUID] = None,
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        处理用户消息
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
            # 阶段 1：意图分类
            intent = await self._classify_intent(user_message)

            # 阶段 2：根据意图路由
            if intent == "todos":
                # 调用 Task Agent Skill
                result = await self._handle_todos(
                    user_message,
                    state.session_id,
                    stream_callback
                )

                # 不记录 Main Agent 的回复（Skill 已经回复）
                return {
                    "success": True,
                    "text": "",  # Main Agent 保持沉默
                    "session_id": str(state.session_id),
                    "intent": "todos"
                }

            else:  # intent == "chat"
                # Main Agent 直接回复
                response = await self._handle_chat(
                    user_message,
                    state,
                    stream_callback
                )

                # 记录 Main Agent 的回复
                state.add_message("assistant", response)

                return {
                    "success": True,
                    "text": response,
                    "session_id": str(state.session_id),
                    "intent": "chat"
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

    async def _classify_intent(self, user_input: str) -> str:
        """
        分类用户意图
        """
        response = await self.llm_client.chat_completion(
            messages=[
                {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.0,
            max_tokens=10,
            stream=False
        )

        # 提取意图
        content = ""
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice and hasattr(choice.delta, 'content') and choice.delta.content:
                content += choice.delta.content

        intent = content.strip().lower()

        # 容错处理
        if "todos" in intent or "task" in intent:
            return "todos"
        else:
            return "chat"

    async def _handle_chat(
        self,
        user_message: str,
        state: AgentState,
        stream_callback
    ) -> str:
        """
        处理日常对话
        """
        # 构建消息历史
        messages = [
            {"role": "system", "content": CHAT_AGENT_PROMPT}
        ]

        # 获取最近 10 条消息
        recent_messages = state.get_recent_messages(limit=10)
        for msg in recent_messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # 调用 LLM
        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.7,
            stream=True
        )

        # 收集流式响应
        content = ""
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue

            delta = choice.delta
            if hasattr(delta, 'content') and delta.content:
                content += delta.content
                if stream_callback:
                    stream_callback('content', delta.content)

        return content

    async def _handle_todos(
        self,
        user_message: str,
        session_id: UUID,
        stream_callback
    ) -> Dict[str, Any]:
        """
        处理任务管理
        """
        from src.agent.task_agent_tool import (
            task_agent_tool,
            format_task_agent_visualization
        )

        # 显示切换可视化
        if stream_callback:
            calling_text = format_task_agent_visualization("calling")
            stream_callback('tool_call', calling_text)

        # 调用 Task Agent
        result = await task_agent_tool(
            db=self.db,
            user_request=user_message,
            session_id=session_id,
            stream_callback=stream_callback,
            use_reasoner=False
        )

        # 显示完成可视化
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

        return result
```

---

## Prompt 定义

```python
# src/agent/prompts.py

# 意图分类 Prompt
INTENT_CLASSIFIER_PROMPT = """判断用户输入的意图类型。

意图类型：
- chat: 日常对话、问候、闲聊、知识问答、感谢等
- todos: 任务管理（创建、查看、更新、删除任务）

只输出意图类型（chat 或 todos），不要解释。"""

# Chat Agent Prompt
CHAT_AGENT_PROMPT = """你是一个友好的 AI 助手。

输出纯文本，不要使用 Markdown 格式。"""

# Task Agent Prompt（保持不变）
GENERAL_AGENT_PROMPT = """..."""
```

---

## 优势对比

### 旧架构（Function Calling）

```
输入 → Main Agent（挂载 todos tool）
        ├─ Tool JSON 噪音：~200 字符
        ├─ 每次调用都传递
        └─ 强制关注 "todos"
```

**问题**：
- Tool description 必须详细（否则判断不准）
- 但越详细，噪音越大
- 无法避免的矛盾

### 新架构（两阶段路由）

```
输入 → 意图分类（无 tools）
        ├─ Prompt：~50 字符
        ├─ 输出：1 个词
        └─ 无噪音

     → Chat Agent（无 tools）
        ├─ Prompt：~20 字符
        └─ 完全泛化

     → Task Agent（独立）
        └─ 专注任务管理
```

**优势**：
- ✅ 意图分类：极简 prompt，无噪音
- ✅ Chat Agent：完全泛化，无 todos 干扰
- ✅ Task Agent：独立运行，不影响 Main Agent
- ✅ 可扩展：轻松添加更多意图类型

---

## 性能分析

### 延迟

- 意图分类：~100ms（max_tokens=10，极快）
- Chat 回复：~1s（正常对话）
- Todos 处理：~2-3s（Task Agent 的正常时间）

**总延迟**：
- Chat 场景：~1.1s（分类 + 回复）
- Todos 场景：~2.1-3.1s（分类 + Task Agent）

**对比旧架构**：
- 旧架构 Chat：~1s（但质量差，有噪音）
- 旧架构 Todos：~2-3s

**结论**：延迟增加可忽略（~100ms），但质量大幅提升

### 成本

- 意图分类：~10 tokens（几乎免费）
- Chat 回复：正常成本
- Todos 处理：正常成本

**结论**：成本增加可忽略

---

## 扩展性

### 添加新意图类型

```python
# 只需修改意图分类 Prompt
INTENT_CLASSIFIER_PROMPT = """判断用户输入的意图类型。

意图类型：
- chat: 日常对话
- todos: 任务管理
- calendar: 日历管理（新增）
- notes: 笔记管理（新增）

只输出意图类型，不要解释。"""

# 添加对应的处理函数
async def _handle_calendar(self, user_message, session_id, stream_callback):
    # 调用 Calendar Agent
    ...
```

**优势**：
- 不需要修改 function calling schema
- 不增加噪音
- 线性扩展

---

## 实施计划

### Step 1：修改 prompts.py

添加新的 prompt 定义

### Step 2：重写 main_agent.py

实现两阶段路由逻辑

### Step 3：测试验证

运行测试场景，验证效果

### Step 4：性能优化

如果意图分类延迟太高，可以考虑：
- 缓存常见输入的意图
- 使用更快的模型（如 GPT-3.5）
- 或者切换到 Embedding-based 路由

---

## 总结

**核心洞察**：
- Function Calling 协议本身就是噪音源
- 打破协议限制，用纯 LLM 做意图分类
- 分离关注点：意图分类 vs 内容生成

**关键优势**：
- ✅ 完全消除 Tool JSON 噪音
- ✅ Main Agent 完全泛化
- ✅ 架构清晰，易扩展
- ✅ 性能损失可忽略

**适用场景**：
- 需要高质量泛化对话的场景
- 需要支持多种意图类型的场景
- 对 prompt 噪音敏感的场景
