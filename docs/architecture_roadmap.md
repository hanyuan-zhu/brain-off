# GauzAssist 架构设计与路线规划

## 核心问题

### Prompt 优化的困境

**实验结果**：
- 优化前：System Prompt 9 字符 + Tool Description 35 字符 = 44 字符
- 优化后：System Prompt 7 字符 + Tool Description 5 字符 = 12 字符
- **噪音减少 73%，但问题依然存在**

**测试场景**：
```
用户: "你好"
Main Agent: "你好！我可以帮你管理待办事项（todos）。你可以告诉我：
- 添加新的待办事项
- 查看现有的待办事项列表
..."

用户: "今天天气真好"
Main Agent: "是的，今天天气确实很好！不过，我目前只能帮你管理待办事项（todos）。"

用户: "什么是 GTD？"
Main Agent: "GTD（Getting Things Done）是...
如果你想开始实践GTD，我可以帮你管理待办事项清单！"
```

**核心问题**：
1. **过度推销 todos**：每次回复都提到 todos，像推销员
2. **使用 Markdown**：违反格式要求（**粗体**、列表符号）
3. **缺乏泛化能力**：无法自然对话

### 根本原因

**Function Calling 协议的固有问题**：

```python
# Main Agent 挂载的工具
{
  "name": "todos",
  "description": "管理 todos"  # 即使只有 5 个字符
}
```

**问题分析**：
- Tool 的存在本身 = 强烈的暗示
- LLM 认为："我是一个 todos 管理系统"
- 无论 description 多简洁，都无法避免
- **这不是 Prompt 的问题，而是架构的问题**

**关键洞察**：
> 只要 Main Agent 直接挂载具体工具（todos），就会产生噪音。
> 无论如何优化 Prompt，都无法让 Main Agent 保持中性。

---

## 解决方案：Tools Router 架构

### 核心思想

**从**：
```
Main Agent 直接挂载 todos
  → LLM 知道有 todos 工具
  → 倾向于推销 todos
```

**到**：
```
Main Agent 挂载 tools_router（中性）
  → LLM 只知道"可以查找工具"
  → 不知道具体有哪些工具
  → 保持完全中性
```

### 三层架构

```
用户输入
    ↓
Main Agent（对话层）
  - Prompt: "输出纯文本。"
  - Tool: tools_router（"查找工具"）
  - 完全中性，不知道有 todos
    ↓
Tools Router（路由层）
  - 根据对话历史搜索工具库
  - 匹配合适的工具
  - 调用并返回结果
    ↓
Tool Registry（工具层）
  - todos: 任务管理 Skill
  - calendar: 日历管理 Skill（未来）
  - notes: 笔记管理 Skill（未来）
  - ...（可扩展到数百上千个工具）
```

### 关键优势

**1. 完全中性的 Main Agent**

```python
# Main Agent 只知道这些
PROMPT = "输出纯文本。"
TOOL = {
  "name": "tools_router",
  "description": "查找工具"  # 不提及任何具体工具
}
```

**噪音分析**：
- System Prompt: 7 字符
- Tool Description: 4 字符
- **总计: 11 字符**
- **不包含任何具体工具信息**

**2. 动态工具发现**

```python
# Tools Router 的工作流程
def route(conversation_history):
    # 1. 搜索工具库
    tools = search_tools(conversation_history)

    # 2. 匹配最合适的工具
    tool = match_best_tool(tools, conversation_history)

    # 3. 调用工具
    result = call_tool(tool, conversation_history)

    return result
```

**3. 无限扩展性**

添加新工具：
```python
# 只需注册到 Tool Registry
registry.register("calendar", {
    "description": "管理日历",
    "handler": calendar_agent_tool
})

# Main Agent 完全不需要修改
# Tools Router 自动发现新工具
```

---

## 架构对比

### 当前架构（有噪音）

```
Main Agent
  ├─ Prompt: "输出纯文本。"
  └─ Tool: todos（"管理 todos"）
       ↓
       问题：LLM 知道有 todos
       结果：过度推销 todos
```

**噪音来源**：
- Tool 的存在 = 噪音
- 无法通过 Prompt 优化解决

### 目标架构（无噪音）

```
Main Agent
  ├─ Prompt: "输出纯文本。"
  └─ Tool: tools_router（"查找工具"）
       ↓
       Tools Router
         └─ 搜索 Tool Registry
              └─ 找到 todos
```

**噪音消除**：
- Main Agent 不知道有 todos
- 完全中性
- 泛化能力恢复

---

## 实施路线

### Phase 1: 核心架构（当前优先级）

**目标**：实现 Tools Router 基础架构

**核心组件**：

1. **Tool Registry**
   - 工具注册表
   - 工具元数据管理
   - 工具搜索接口

2. **Tools Router Agent**
   - 工具发现和匹配
   - 工具调用
   - 结果返回

3. **Tools Router Tool Schema**
   - 定义 tools_router 工具
   - 极简 description

4. **Main Agent 修改**
   - 挂载 tools_router
   - 移除 todos 直接挂载

**验证标准**：
- ✅ Main Agent 不知道有 todos
- ✅ 泛化对话自然（不推销 todos）
- ✅ 任务管理功能正常
- ✅ 对话历史干净

---

### Phase 2: 工具发现优化

**目标**：支持更多工具，提升匹配准确率

**策略演进**：

1. **简单匹配**（Phase 1）
   ```python
   # LLM 根据工具描述匹配
   prompt = f"可用工具：{tools_list}\n选择最合适的工具"
   tool = llm.generate(prompt)
   ```
   - 优点：简单、快速
   - 缺点：工具多时效率低

2. **语义搜索**（Phase 2）
   ```python
   # Embedding 相似度匹配
   user_embedding = embed(user_input)
   tool_embeddings = [embed(tool.description) for tool in tools]
   best_tool = max_similarity(user_embedding, tool_embeddings)
   ```
   - 优点：快速、可扩展到数百工具
   - 缺点：需要维护 Embedding 索引

3. **Preview 测试**（未来）
   ```python
   # 实际调用测试
   candidates = top_k_tools(user_input)
   results = [preview(tool, user_input) for tool in candidates]
   best_tool = select_by_preview_result(results)
   ```
   - 优点：准确率高
   - 缺点：延迟高、成本高

---

### Phase 3: 高级功能

**1. 工具组合**

场景：
```
用户: "创建一个任务并添加到日历"
→ Tools Router 返回: [todos, calendar]
→ 依次调用并合并结果
```

**2. Graph 路由**

使用知识图谱建模工具关系：
```
todos → calendar（任务可以关联日历）
notes → web_search（笔记可以引用搜索结果）
```

**3. 动态工具生成**

根据用户需求动态生成工具：
```
用户: "我需要一个计算复利的工具"
→ LLM 生成工具代码
→ 自动测试和注册
→ 立即可用
```

---

## 关键设计原则

### 1. 极简噪音

**原则**：每个组件的 prompt 和 tool description 都要极简

**反例**：
```python
# ❌ 冗长的 description
"管理用户的 todos。处理 todos 的创建、搜索、更新、删除等操作。"
```

**正例**：
```python
# ✅ 极简 description
"查找工具"
```

### 2. 中性路由

**原则**：Main Agent 不知道具体有哪些工具

**实现**：
- Main Agent 只挂载 tools_router
- tools_router 的 description 不提及具体工具
- 工具信息只存在于 Tool Registry

### 3. 工具发现

**原则**：通过 Tools Router 动态发现和匹配工具

**好处**：
- 添加新工具不影响 Main Agent
- 支持数百上千个工具
- 可以切换不同的匹配策略

### 4. 无限扩展

**原则**：添加新工具不影响现有架构

**实现**：
```python
# 添加新工具只需要注册
registry.register("new_tool", {...})

# Main Agent 完全不需要修改
# Tools Router 自动发现
```

---

## 总结

### 核心洞察

1. **Prompt 优化有极限**
   - 即使优化到 12 字符，问题依然存在
   - 根本原因：Tool 的存在本身就是噪音

2. **架构才是解决方案**
   - Tools Router 架构消除噪音源头
   - Main Agent 保持完全中性
   - 泛化能力恢复

3. **扩展性是关键**
   - 支持数百上千个工具
   - 添加工具不影响架构
   - 可以演进匹配策略

### 下一步

**立即实施 Tools Router 架构**，而不是继续优化 Prompt。

原因：
- Prompt 优化已到极限
- 问题依然存在
- Tools Router 才是根本解决方案
