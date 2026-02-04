#!/usr/bin/env python3
"""
测试文件操作工具
"""

import os
import tempfile
from services.kimi_agent_tools import (
    list_files,
    read_file,
    write_file,
    append_to_file
)


def test_file_tools():
    """测试文件操作工具"""

    # 创建临时工作目录
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 临时工作目录: {temp_dir}\n")

        # 测试 1: list_files (空目录)
        print("=" * 50)
        print("测试 1: list_files (空目录)")
        print("=" * 50)
        result = list_files(temp_dir)
        print(f"结果: {result}")
        assert result["success"] == True
        assert result["data"]["count"] == 0
        print("✅ 通过\n")

        # 测试 2: write_file (创建新文件)
        print("=" * 50)
        print("测试 2: write_file (创建新文件)")
        print("=" * 50)
        result = write_file(temp_dir, "notes.md", "# 分析笔记\n\n这是第一行内容。")
        print(f"结果: {result}")
        assert result["success"] == True
        print("✅ 通过\n")

        # 测试 3: list_files (有文件)
        print("=" * 50)
        print("测试 3: list_files (有文件)")
        print("=" * 50)
        result = list_files(temp_dir)
        print(f"结果: {result}")
        assert result["success"] == True
        assert result["data"]["count"] == 1
        assert result["data"]["files"][0]["name"] == "notes.md"
        print("✅ 通过\n")

        # 测试 4: read_file
        print("=" * 50)
        print("测试 4: read_file")
        print("=" * 50)
        result = read_file(temp_dir, "notes.md")
        print(f"结果: {result}")
        assert result["success"] == True
        assert "分析笔记" in result["data"]["content"]
        print("✅ 通过\n")

        # 测试 5: append_to_file
        print("=" * 50)
        print("测试 5: append_to_file")
        print("=" * 50)
        result = append_to_file(temp_dir, "notes.md", "\n\n## 新增内容\n\n这是追加的内容。")
        print(f"结果: {result}")
        assert result["success"] == True
        print("✅ 通过\n")

        # 测试 6: read_file (验证追加)
        print("=" * 50)
        print("测试 6: read_file (验证追加)")
        print("=" * 50)
        result = read_file(temp_dir, "notes.md")
        print(f"内容:\n{result['data']['content']}")
        assert result["success"] == True
        assert "新增内容" in result["data"]["content"]
        assert "追加的内容" in result["data"]["content"]
        print("✅ 通过\n")

        # 测试 7: write_file (覆盖)
        print("=" * 50)
        print("测试 7: write_file (覆盖)")
        print("=" * 50)
        result = write_file(temp_dir, "notes.md", "# 新笔记\n\n完全覆盖了旧内容。")
        print(f"结果: {result}")
        assert result["success"] == True
        print("✅ 通过\n")

        # 测试 8: read_file (验证覆盖)
        print("=" * 50)
        print("测试 8: read_file (验证覆盖)")
        print("=" * 50)
        result = read_file(temp_dir, "notes.md")
        print(f"内容:\n{result['data']['content']}")
        assert result["success"] == True
        assert "新笔记" in result["data"]["content"]
        assert "分析笔记" not in result["data"]["content"]
        print("✅ 通过\n")

        # 测试 9: 创建多个文件
        print("=" * 50)
        print("测试 9: 创建多个文件")
        print("=" * 50)
        write_file(temp_dir, "log.md", "# 日志\n")
        write_file(temp_dir, "plan.md", "# 计划\n")
        result = list_files(temp_dir)
        print(f"结果: {result}")
        assert result["data"]["count"] == 3
        print("✅ 通过\n")

        print("=" * 50)
        print("🎉 所有测试通过！")
        print("=" * 50)


if __name__ == "__main__":
    test_file_tools()
