# Skill文件系统加载设计

## 1. 文件夹结构

```
skills/
├── todo/
│   ├── skill.md              # Skill prompt内容
│   ├── config.json           # 配置文件
│   └── tools.py              # 工具实现（可选，如果需要自定义工具）
├── cost/
│   ├── skill.md
│   ├── config.json
│   └── tools/                # 复杂skill可以有工具子文件夹
│       ├── vision_service.py
│       ├── rendering_service.py
│       └── ...
└── research/
    ├── skill.md
    └── config.json
```

## 2. skill.md 格式

Markdown文件，直接包含skill的system prompt内容：

```markdown
# Task Management Assistant

You are a professional task management assistant. Your role is to help users:
- Create and organize tasks
- Track task progress
- Manage priorities and deadlines
- Provide productivity insights

## Guidelines
- Always confirm before deleting tasks
- Use clear, concise language
- Suggest task breakdowns for complex items
```

## 3. config.json Schema

```json
{
  "id": "todo",
  "name": "Task Management",
  "version": "1.0.0",
  "description": "Manages tasks and todos",
  "tools": [
    "database_operation",
    "search"
  ],
  "model": {
    "provider": "deepseek",
    "model_name": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 4000
  },
  "enabled": true,
  "metadata": {
    "author": "System",
    "created_at": "2025-01-01",
    "tags": ["productivity", "task-management"]
  }
}
```

### 字段说明

- **id** (required): 唯一标识符
- **name** (required): 显示名称
- **version** (optional): 版本号
- **description** (optional): 描述
- **tools** (required): 工具名称数组
- **model** (optional): 模型配置，如果不指定则使用默认模型
  - `provider`: 模型提供商 (deepseek, openai, etc.)
  - `model_name`: 具体模型名称
  - `temperature`: 温度参数
  - `max_tokens`: 最大token数
- **enabled** (optional): 是否启用，默认true
- **metadata** (optional): 元数据

## 4. 加载优先级

1. **文件系统优先**: 如果 `skills/` 文件夹存在对应skill，优先从文件系统加载
2. **数据库回退**: 如果文件系统不存在，从数据库加载
3. **自动同步**: 启动时可选择将文件系统skill同步到数据库

## 5. 实现组件

### FileSystemSkillLoader
- 扫描 `skills/` 文件夹
- 解析 `skill.md` 和 `config.json`
- 生成embedding
- 返回Skill对象

### SkillService扩展
- 添加 `load_from_filesystem()` 方法
- 添加 `sync_to_database()` 方法
- 修改 `retrieve_skills()` 支持混合加载

## 6. 配置选项

在 `src/infrastructure/config.py` 添加：

```python
SKILL_FILESYSTEM_ENABLED = True
SKILL_FILESYSTEM_PATH = "skills"
SKILL_AUTO_SYNC_TO_DB = True  # 启动时自动同步
```
