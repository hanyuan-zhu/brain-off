"""
DWG 到 DXF 转换服务 - 基于 ODA File Converter

使用免费的 ODA File Converter 进行本地转换，无需网络访问
下载地址: https://www.opendesign.com/guestfiles/oda_file_converter
"""

import os
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List


class ODAConverter:
    """ODA File Converter 包装器"""

    def __init__(self, oda_path: Optional[str] = None):
        """
        初始化 ODA 转换器

        Args:
            oda_path: ODA File Converter 可执行文件路径
                     如果为 None，会自动搜索常见安装位置
        """
        self.oda_path = oda_path or self._find_oda_converter()

    def _find_oda_converter(self) -> Optional[str]:
        """
        自动查找 ODA File Converter 安装路径

        Returns:
            可执行文件路径，如果未找到返回 None
        """
        # macOS 常见安装位置
        possible_paths = [
            "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
            "/usr/local/bin/ODAFileConverter",
            os.path.expanduser("~/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"),
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path

        return None

    def is_available(self) -> bool:
        """检查 ODA File Converter 是否可用"""
        return self.oda_path is not None and os.path.exists(self.oda_path)

    def convert_dwg_to_dxf(
        self,
        dwg_path: str,
        output_path: Optional[str] = None,
        dxf_version: str = "ACAD2018",
        recursive: bool = False,
        audit: bool = True
    ) -> Dict[str, Any]:
        """
        将 DWG 文件转换为 DXF 格式

        Args:
            dwg_path: DWG 文件路径（可以是文件或目录）
            output_path: 输出路径（文件或目录）
            dxf_version: DXF 版本 (ACAD9, ACAD10, ACAD12, ACAD13, ACAD14,
                        ACAD2000, ACAD2004, ACAD2007, ACAD2010, ACAD2013, ACAD2018)
            recursive: 是否递归处理子目录
            audit: 是否在转换前审计文件

        Returns:
            Dict 包含:
            - success: bool
            - data: {output_path: str, files_converted: int}
            - error: str (如果失败)
        """
        try:
            # 检查 ODA Converter 是否可用
            if not self.is_available():
                return {
                    "success": False,
                    "error": "ODA File Converter 未安装。请从以下地址下载: https://www.opendesign.com/guestfiles/oda_file_converter"
                }

            # 检查输入文件/目录是否存在
            if not os.path.exists(dwg_path):
                return {
                    "success": False,
                    "error": f"文件或目录不存在: {dwg_path}"
                }

            # 确定输入和输出路径
            input_is_file = os.path.isfile(dwg_path)

            if input_is_file:
                # 单文件转换
                if not dwg_path.lower().endswith('.dwg'):
                    return {
                        "success": False,
                        "error": f"不是 DWG 文件: {dwg_path}"
                    }

                # 确定输出路径
                if output_path is None:
                    output_path = dwg_path.rsplit('.', 1)[0] + '.dxf'

                # 创建临时目录用于转换
                with tempfile.TemporaryDirectory() as temp_dir:
                    # 复制文件到临时目录
                    import shutil
                    temp_input = os.path.join(temp_dir, "input")
                    temp_output = os.path.join(temp_dir, "output")
                    os.makedirs(temp_input)
                    os.makedirs(temp_output)

                    temp_dwg = os.path.join(temp_input, os.path.basename(dwg_path))
                    shutil.copy2(dwg_path, temp_dwg)

                    # 执行转换
                    result = self._run_conversion(
                        temp_input,
                        temp_output,
                        dxf_version,
                        recursive=False,
                        audit=audit
                    )

                    if not result["success"]:
                        return result

                    # 复制转换后的文件
                    converted_files = list(Path(temp_output).glob("*.dxf"))
                    if not converted_files:
                        return {
                            "success": False,
                            "error": "转换失败：未生成 DXF 文件"
                        }

                    shutil.copy2(str(converted_files[0]), output_path)

                    file_size = os.path.getsize(output_path)

                    return {
                        "success": True,
                        "data": {
                            "output_path": output_path,
                            "file_size": file_size,
                            "converter": "oda"
                        }
                    }

            else:
                # 目录批量转换
                if output_path is None:
                    output_path = os.path.join(os.path.dirname(dwg_path), "converted")

                os.makedirs(output_path, exist_ok=True)

                result = self._run_conversion(
                    dwg_path,
                    output_path,
                    dxf_version,
                    recursive=recursive,
                    audit=audit
                )

                if result["success"]:
                    # 统计转换的文件数
                    converted_files = list(Path(output_path).rglob("*.dxf") if recursive else Path(output_path).glob("*.dxf"))
                    result["data"]["files_converted"] = len(converted_files)

                return result

        except Exception as e:
            return {
                "success": False,
                "error": f"转换失败: {str(e)}"
            }

    def _run_conversion(
        self,
        input_dir: str,
        output_dir: str,
        output_version: str,
        recursive: bool = False,
        audit: bool = True
    ) -> Dict[str, Any]:
        """
        执行 ODA File Converter 转换

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            output_version: 输出版本
            recursive: 是否递归
            audit: 是否审计

        Returns:
            转换结果
        """
        try:
            # 构建命令行参数
            # 格式: "Input Folder" "Output Folder" Output_version {Output_File_type} Recurse_Input_Folder Audit_each_file
            cmd = [
                self.oda_path,
                input_dir,           # Quoted Input Folder
                output_dir,          # Quoted Output Folder
                output_version,      # Output_version (ACAD2018, etc.)
                "DXF",              # Output File type
                "1" if recursive else "0",  # Recurse Input Folder
                "1" if audit else "0"       # Audit each file
            ]

            # 执行转换
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"ODA 转换失败: {result.stderr or result.stdout}"
                }

            return {
                "success": True,
                "data": {
                    "output_path": output_dir
                }
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "转换超时（超过5分钟）"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"执行转换失败: {str(e)}"
            }


# 全局转换器实例
_converter = None


def get_converter() -> ODAConverter:
    """获取全局转换器实例"""
    global _converter
    if _converter is None:
        _converter = ODAConverter()
    return _converter


def convert_dwg_to_dxf(
    dwg_path: str,
    output_path: Optional[str] = None,
    dxf_version: str = "ACAD2018",
    **kwargs
) -> Dict[str, Any]:
    """
    便捷函数：将 DWG 文件转换为 DXF 格式

    Args:
        dwg_path: DWG 文件路径
        output_path: 输出 DXF 文件路径（可选）
        dxf_version: DXF 版本（默认 ACAD2018）
        **kwargs: 其他参数传递给 ODAConverter.convert_dwg_to_dxf

    Returns:
        Dict 包含转换结果
    """
    converter = get_converter()
    return converter.convert_dwg_to_dxf(
        dwg_path,
        output_path,
        dxf_version,
        **kwargs
    )
