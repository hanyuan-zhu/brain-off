# AI-Native Task Management System

一个以 Chatbot 为核心的 AI 原生任务管理系统。所有任务操作（创建、查询、更新、讨论）都通过 AI Agent 对话完成。

## 核心特性

### 🎯 灵感孵化（Inspiration Incubation）
- 随意倾倒零碎想法，AI 自动整理、打标并存入数据库
- AI 智能聚类和主题提取
- 一键将想法转换为可执行任务

### 🔍 动态查询（Dynamic Querying）
- 通过对话询问："最近有什么紧急的事？"
- 语义搜索："我之前关于财务有什么想法？"
- AI 负责检索并总结回复

### 💬 深度讨论（Deep Discussion）
- AI 根据现有任务提供建议
- 协助细化任务边界和交付要求
- 保存对话历史供后续参考

## 技术栈

- **Backend**: FastAPI + SQLAlchemy 2.0 + PostgreSQL + pgvector
- **AI**: DeepSeek API (LLM) + DashScope API (Embeddings)
- **Frontend**: Streamlit (对话界面)
- **Database**: PostgreSQL with pgvector extension

## 项目结构

```
chatbot/
├── src/
│   ├── database/       # 数据库模型和连接
│   ├── repositories/   # 数据访问层
│   ├── services/       # 业务逻辑层
│   ├── agent/          # AI Agent 核心
│   ├── llm/            # LLM 客户端
│   ├── api/            # FastAPI 路由
│   └── utils/          # 工具函数
├── tests/              # 测试文件
├── scripts/            # 脚本工具
├── ui/                 # Streamlit UI
└── alembic/            # 数据库迁移
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- PostgreSQL 14+ (with pgvector extension)
- DeepSeek API Key
- DashScope API Key

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.template` 到 `.env` 并填写配置：

```bash
cp .env.template .env
```

编辑 `.env` 文件：

```bash
# Application Configuration
APP_ENV=development
LOG_LEVEL=INFO
SECRET_KEY=your_secret_key_here

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot

# DeepSeek API Configuration (for LLM)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# DashScope API Configuration (for Embeddings)
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
```

### 4. 设置 PostgreSQL 数据库

#### 安装 PostgreSQL (如果还没有安装)

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql-14 postgresql-contrib
sudo systemctl start postgresql
```

#### 创建数据库

```bash
# 连接到 PostgreSQL
psql postgres

# 创建数据库
CREATE DATABASE chatbot;

# 创建用户（可选）
CREATE USER chatbot_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE chatbot TO chatbot_user;

# 退出
\q
```

#### 安装 pgvector 扩展

```bash
# macOS
brew install pgvector

# Ubuntu/Debian
sudo apt-get install postgresql-14-pgvector
```

### 5. 初始化数据库

```bash
python scripts/init_db.py
```

这个脚本会：
- 创建 pgvector 扩展
- 创建所有数据表（tasks, ideas, tags, conversations 等）

### 6. 运行项目

目前 Phase 1 已完成，数据库基础设施已就绪。后续阶段将实现：

- **Phase 2**: Embedding 服务和语义搜索
- **Phase 3**: LLM 集成（DeepSeek API）
- **Phase 4**: 灵感孵化核心功能
- **Phase 5**: Agent 实现（Query → Thoughts → Actions → Review）
- **Phase 6**: 任务管理功能
- **Phase 7**: Streamlit UI

## 数据库架构

### 核心表

1. **tasks** - 任务表
   - 支持状态、优先级、能量等级
   - 向量嵌入用于语义搜索
   - AI 生成的摘要和置信度分数

2. **ideas** - 想法表
   - 捕获原始、未结构化的想法
   - 处理后的内容和状态跟踪
   - 转换为任务的关联

3. **tags** - 标签表
   - 任务分类和组织
   - 使用计数用于推荐

4. **task_tags** - 任务-标签关联表

5. **task_relationships** - 任务关系表
   - 支持 blocks, depends_on, subtask_of 等关系

6. **conversations** - 对话历史表
   - 保存用户和 AI 的对话
   - 记录 AI 的思考过程和使用的工具

7. **agent_sessions** - Agent 会话表
   - 跟踪对话会话和上下文

## Agent 工具集（21 个工具）

### 任务管理 (4 tools)
- create_task, update_task, delete_task, get_task_by_id

### 查询搜索 (3 tools)
- search_tasks, get_task_context, aggregate_tasks

### 标签管理 (4 tools)
- create_or_get_tag, add_tags_to_task, remove_tags_from_task, suggest_tags

### 关系管理 (2 tools)
- create_task_relationship, get_related_tasks

### 灵感孵化 (4 tools)
- capture_idea, process_ideas, convert_idea_to_task, search_ideas

### 对话上下文 (2 tools)
- save_conversation, get_conversation_history

### 智能建议 (2 tools)
- suggest_next_actions, analyze_task_patterns

## 开发进度

- [x] Phase 1: 基础设施搭建
  - [x] 项目结构
  - [x] 数据库模型
  - [x] 连接和会话管理
  - [x] 基础仓库模式
- [ ] Phase 2: Embedding 和搜索基础
- [ ] Phase 3: LLM 集成
- [ ] Phase 4: 灵感孵化核心
- [ ] Phase 5: Agent 实现
- [ ] Phase 6: 任务管理
- [ ] Phase 7: Streamlit UI

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
