# Brain-Off AI Task Manager

把任务扔给 AI，让它帮你记录、拆分、管理。

未来会挂载各种工具 Agent，成为你的全能助手。

## 安装

**推荐使用 Claude Code 或 Cursor 等 AI 工具来安装配置。**

### 给 AI 的安装要点

1. **环境**: Python 3.10+, PostgreSQL 14+ (需要 pgvector 扩展)
2. **依赖**: `pip install -r requirements.txt`
3. **配置**: 复制 `.env.template` 到 `.env`，填写 `DEEPSEEK_API_KEY` 和 `DASHSCOPE_API_KEY`
4. **数据库**: 创建 `chatbot` 数据库，运行 `python scripts/init_db.py`
5. **启动**: `python chat.py`

### 了解架构

用 Claude Code、Cursor 等 AI 工具自己分析代码就行。

## 许可证

MIT License
