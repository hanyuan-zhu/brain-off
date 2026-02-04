# ODA File Converter 使用指南

## ✅ 安装完成

ODA File Converter 已成功安装到：
```
/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter
```

## 📖 使用方法

### 1. Python API 使用

```python
from services.oda_converter import convert_dwg_to_dxf

# 转换单个文件
result = convert_dwg_to_dxf(
    dwg_path="input.dwg",
    output_path="output.dxf",  # 可选，默认同目录
    dxf_version="ACAD2018"     # 可选，默认 ACAD2018
)

if result["success"]:
    print(f"✓ 转换成功: {result['data']['output_path']}")
    print(f"  文件大小: {result['data']['file_size']} bytes")
else:
    print(f"✗ 转换失败: {result['error']}")
```

### 2. 命令行测试

```bash
# 检查安装状态
python test_oda_converter.py

# 转换 DWG 文件
python test_oda_converter.py /path/to/your/file.dwg
```

### 3. 支持的 DXF 版本

- ACAD9
- ACAD10
- ACAD12
- ACAD13
- ACAD14
- ACAD2000
- ACAD2004
- ACAD2007
- ACAD2010
- ACAD2013
- ACAD2018 (默认)

### 4. 高级用法

```python
from services.oda_converter import ODAConverter

# 创建转换器实例
converter = ODAConverter()

# 批量转换目录中的所有 DWG 文件
result = converter.convert_dwg_to_dxf(
    dwg_path="/path/to/dwg/folder",
    output_path="/path/to/output/folder",
    dxf_version="ACAD2018",
    recursive=True,  # 递归处理子目录
    audit=True       # 转换前审计文件
)

if result["success"]:
    print(f"✓ 批量转换成功")
    print(f"  转换文件数: {result['data']['files_converted']}")
```

## 🔄 替换旧的 Selenium 方案

如果你之前使用的是 `services/dwg_converter.py`（基于 Selenium），现在可以直接替换为 ODA 方案：

```python
# 旧方案（Selenium，有限制）
from services.dwg_converter import convert_dwg_to_dxf

# 新方案（ODA，无限制）
from services.oda_converter import convert_dwg_to_dxf

# API 完全兼容，直接替换即可
result = convert_dwg_to_dxf("input.dwg")
```

## ✨ 优势对比

| 特性 | ODA File Converter | Selenium 在线转换 |
|------|-------------------|------------------|
| 转换速度 | ⚡ 快速（本地） | 🐌 慢（需上传下载） |
| 网络依赖 | ✅ 无需网络 | ❌ 必须联网 |
| 使用限制 | ✅ 无限制 | ❌ 每日/每小时限制 |
| 稳定性 | ✅ 高 | ❌ 依赖网站可用性 |
| 批量转换 | ✅ 支持 | ❌ 不支持 |
| 版本支持 | ✅ 全版本 | ⚠️ 有限 |
| 隐私安全 | ✅ 本地处理 | ⚠️ 需上传到服务器 |

## 📝 注意事项

1. **首次运行可能需要授权**
   - macOS 可能会提示"无法验证开发者"
   - 解决方法：系统设置 → 隐私与安全性 → 允许运行

2. **支持的文件格式**
   - 输入：DWG (所有版本)
   - 输出：DXF, DWG

3. **性能建议**
   - 大文件（>100MB）转换可能需要几分钟
   - 批量转换建议使用 `recursive=True`

## 🔗 相关链接

- ODA File Converter 官网: https://www.opendesign.com/guestfiles/oda_file_converter
- 源代码: `services/oda_converter.py`
- 测试脚本: `test_oda_converter.py`

## 🚀 快速开始

```bash
# 1. 验证安装
python test_oda_converter.py

# 2. 转换你的第一个 DWG 文件
python test_oda_converter.py your_file.dwg

# 3. 在代码中使用
python -c "from services.oda_converter import convert_dwg_to_dxf; print(convert_dwg_to_dxf('test.dwg'))"
```
