"""
工具注册表 - 统一管理所有工具

功能：
1. 注册工具（schema + function）
2. 根据技能领域获取工具
3. 执行工具调用
4. 格式化工具可视化
"""
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        # 工具存储: {tool_name: {schema, function, visualization}}
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        schema: Dict[str, Any],
        function: Callable,
        visualization: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            schema: 工具 schema（用于 LLM function calling）
            function: 工具函数
            visualization: 可视化模板（可选）
        """
        self.tools[name] = {
            "schema": schema,
            "function": function,
            "visualization": visualization or {}
        }

    def get_tools_by_names(self, tool_names: List[str]) -> List[Dict[str, Any]]:
        """
        根据工具名称列表获取工具 schemas

        Args:
            tool_names: 工具名称列表

        Returns:
            工具 schema 列表
        """
        return [
            self.tools[name]["schema"]
            for name in tool_names
            if name in self.tools
        ]

    def get_default_tools(self) -> List[Dict[str, Any]]:
        """
        获取默认工具集

        Returns:
            默认工具 schema 列表
        """
        default_tool_names = ["database_operation", "search"]
        return self.get_tools_by_names(default_tool_names)

    async def execute_tool(
        self,
        tool_name: str,
        db: AsyncSession,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行工具

        Args:
            tool_name: 工具名称
            db: 数据库会话
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        tool_function = self.tools[tool_name]["function"]

        try:
            # 检查工具函数是否需要 db 参数
            import inspect
            sig = inspect.signature(tool_function)
            needs_db = 'db' in sig.parameters

            if needs_db:
                result = await tool_function(db, **kwargs)
            else:
                result = await tool_function(**kwargs) if inspect.iscoroutinefunction(tool_function) else tool_function(**kwargs)

            # If tool already follows the standard result envelope, keep it as-is.
            if isinstance(result, dict) and "success" in result and ("data" in result or "error" in result):
                return result

            # Backward compatibility: tools that return {"error": "..."} without envelope.
            if isinstance(result, dict) and isinstance(result.get("error"), str):
                return {"success": False, "error": result["error"]}

            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def format_visualization(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        stage: str = "calling"
    ) -> str:
        """
        格式化工具可视化文本

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            stage: 阶段（calling, success, error）

        Returns:
            格式化后的可视化文本
        """
        if tool_name not in self.tools:
            return f"[调用工具: {tool_name}]"

        visualization = self.tools[tool_name].get("visualization")
        if not visualization:
            return f"[调用工具: {tool_name}]"

        # 通用模板处理（适用于大多数工具）
        if isinstance(visualization, dict) and stage in visualization:
            template = visualization[stage]
            try:
                return template.format(**arguments)
            except (KeyError, ValueError):
                # 如果格式化失败，返回模板本身
                return template

        # 对于 database_operation，获取操作特定的模板
        if tool_name == "database_operation":
            operation = arguments.get("operation", "")
            op_viz = visualization.get(operation, {})
            template = op_viz.get(stage, "")

            if not template:
                return f"[{operation}]"

            # 提取数据用于格式化
            task_data = arguments.get("task_data", {})
            title = arguments.get("title", task_data.get("title", ""))

            try:
                return template.format(
                    title=title,
                    error=arguments.get("error", "")
                )
            except KeyError:
                return template

        # 对于 search 工具
        elif tool_name == "search":
            template = visualization.get(stage, "")
            if not template:
                return "[搜索]"

            try:
                return template.format(
                    query=arguments.get("query", ""),
                    count=arguments.get("count", 0),
                    error=arguments.get("error", "")
                )
            except KeyError:
                return template

        return f"[调用工具: {tool_name}]"


# 全局工具注册表实例
_tool_registry = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表实例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
