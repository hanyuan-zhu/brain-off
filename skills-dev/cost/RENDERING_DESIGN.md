# CAD 渲染方案设计 - 基于坐标的渐进式渲染

## 🎯 设计目标

解决传统固定 DPI 渲染的问题：
- ❌ 固定 DPI 无法适应不同查看需求
- ❌ 稀疏空间导致有效内容占比小
- ❌ 文件大但清晰度不够

采用**基于坐标的渐进式渲染**方案：
- ✅ Agent 可以像人一样"先看全局，再看细节"
- ✅ 按需渲染，自适应清晰度
- ✅ 只渲染有效区域，避免浪费

---

## 🔧 核心工具设计

### 1. get_drawing_bounds() - 获取图纸边界

**功能**: 分析图纸，识别有效区域和关键区域

**输入**:
- `file_path`: DXF 文件路径
- `layers`: 可选的图层过滤

**输出**:
```python
{
    "success": True,
    "bounds": {
        "min_x": 0,
        "min_y": 0,
        "max_x": 50000,
        "max_y": 30000,
        "width": 50000,
        "height": 30000
    },
    "regions": [
        {
            "name": "主建筑区域",
            "bbox": {
                "x": 1000,
                "y": 2000,
                "width": 20000,
                "height": 15000
            },
            "entity_count": 500,
            "density": 0.025,  # 实体密度
            "layers": ["WALL", "COLUMN"],
            "priority": 1  # 优先级（1=高，2=中，3=低）
        }
    ]
}
```

**用途**: Agent 先了解图纸布局，决定渲染策略

---

### 2. render_drawing_region() - 渲染指定区域

**功能**: 渲染 CAD 坐标系中的指定区域，输出固定尺寸的高清图片

**输入**:
- `file_path`: DXF 文件路径
- `bbox`: CAD 坐标边界框 `{"x": 1000, "y": 2000, "width": 5000, "height": 3000}`
- `output_size`: 输出图片尺寸（像素），默认 `(2048, 2048)`
- `layers`: 要渲染的图层列表
- `format`: 输出格式（png/jpg）

**输出**:
```python
{
    "success": True,
    "image_path": "/path/to/region_1000_2000_5000_3000.png",
    "actual_bbox": {
        "x": 1000,
        "y": 2000,
        "width": 5000,
        "height": 3000
    },
    "scale": 0.4096,  # 像素/mm 比例
    "output_size": [2048, 2048],
    "layers_rendered": ["WALL", "TEXT", "DIM"]
}
```

**关键特性**:
- 输入：CAD 坐标（矢量空间）
- 输出：固定尺寸的高清图片
- 自动计算缩放比例
- 确保文字和线条清晰可读

---

### 3. render_drawing_overview() - 渲染全图概览

**功能**: 渲染整个图纸的低分辨率概览

**输入**:
- `file_path`: DXF 文件路径
- `output_size`: 输出尺寸，默认 `(1024, 1024)`
- `layers`: 可选的图层过滤

**输出**:
```python
{
    "success": True,
    "image_path": "/path/to/overview.png",
    "bounds": {...},
    "scale": 0.02048,
    "output_size": [1024, 1024]
}
```

**用途**: 提供全局视图，帮助 Agent 理解整体布局

---

## 🔄 Agent 工作流程

### 典型场景：分析建筑图纸

```
第 1 步：了解图纸范围
├─ Agent: 调用 get_drawing_bounds()
├─ 返回: 图纸 50000×30000 mm，识别 3 个关键区域
└─ Agent: "这是一个大型图纸，有主建筑区、标注区、说明区"

第 2 步：查看全图概览
├─ Agent: 调用 render_drawing_overview(output_size=(1024, 1024))
├─ 返回: 全图概览图片
├─ Agent: 使用 analyze_drawing_visual() 分析
└─ Agent: "看到整体布局，但墙体标注看不清楚"

第 3 步：放大关键区域
├─ Agent: "需要看清楚主建筑区的墙体标注"
├─ Agent: 调用 render_drawing_region(
│           bbox={x:1000, y:2000, width:5000, height:3000},
│           output_size=(2048, 2048)
│         )
├─ 返回: 该区域的高清图片（2048×2048）
├─ Agent: 使用 analyze_drawing_visual() 分析
└─ Agent: "识别到：墙厚 200mm，但还有个小字看不清"

第 4 步：进一步放大细节
├─ Agent: "需要看清楚那个小字"
├─ Agent: 调用 render_drawing_region(
│           bbox={x:2000, y:2500, width:1000, height:800},
│           output_size=(2048, 2048)  # 更小区域，同样尺寸 = 更高清晰度
│         )
├─ 返回: 局部放大图片
├─ Agent: 使用 analyze_drawing_visual() 分析
└─ Agent: "识别到：C30 混凝土"

第 5 步：系统扫描
├─ Agent: 遍历所有关键区域
├─ 对每个区域：渲染 → 分析 → 提取信息
└─ 汇总所有信息，生成工程量清单
```

---

## 💡 技术实现要点

### 1. 智能区域识别算法

```python
def identify_key_regions(doc, msp, grid_size=1000):
    """
    自动识别图纸中的关键区域

    策略:
    1. 网格划分，统计每个网格的实体密度
    2. 聚类高密度区域
    3. 识别标注集中区域
    4. 过滤稀疏噪点
    """
```

**步骤**:
1. 将图纸划分为 1000mm × 1000mm 的网格
2. 统计每个网格的实体数量
3. 使用密度阈值过滤低密度网格
4. 合并相邻的高密度网格形成区域
5. 按密度排序，标记优先级

---

### 2. 自适应缩放计算

```python
def calculate_optimal_scale(bbox, output_size, min_text_height=20):
    """
    计算最优缩放比例

    确保:
    1. 文字清晰可读（最小字高 >= 20 像素）
    2. 线条清晰（最小线宽 >= 2 像素）
    3. 充分利用输出尺寸
    """
```

**逻辑**:
- 计算宽度和高度的缩放比例
- 取较小值以保持宽高比
- 检查最小文字高度，确保可读性
- 如果文字太小，调整缩放或提示需要放大

---

### 3. 渲染优化

**性能优化**:
- 只渲染指定区域的实体（空间索引）
- 按图层过滤，减少渲染量
- 缓存渲染结果（相同区域不重复渲染）

**质量优化**:
- 使用抗锯齿
- 线条宽度自适应缩放
- 文字大小自适应缩放

---

## 📊 渲染策略对比

### 传统方案 vs 新方案

| 特性 | 传统固定 DPI | 基于坐标渐进式 |
|------|-------------|---------------|
| 清晰度 | 固定，无法调整 | 按需调整，可放大 |
| 文件大小 | 大（包含稀疏空间） | 小（只渲染有效区域） |
| 灵活性 | 低 | 高（Agent 可主动放大） |
| 存储 | 一次生成全部 | 按需生成 |
| 适用场景 | 小图纸 | 大型复杂图纸 |

---

## 🎯 实现优先级

### Phase 1: 核心功能（本周）
1. ✅ `get_drawing_bounds()` - 获取边界和区域
2. ✅ `render_drawing_region()` - 渲染指定区域
3. ✅ `render_drawing_overview()` - 渲染全图概览

### Phase 2: 优化增强（下周）
4. 智能区域识别算法优化
5. 渲染缓存机制
6. 多图层渲染支持

### Phase 3: 集成测试
7. 与 AI 视觉分析集成
8. 端到端测试
9. 性能优化

---

## 📝 使用示例

### 示例 1: Agent 分析图纸

```python
# Step 1: 了解图纸
bounds = get_drawing_bounds("building.dxf")
print(f"图纸范围: {bounds['bounds']['width']} × {bounds['bounds']['height']} mm")
print(f"识别到 {len(bounds['regions'])} 个关键区域")

# Step 2: 查看全图
overview = render_drawing_overview("building.dxf", output_size=(1024, 1024))
analysis = analyze_drawing_visual(overview["image_path"], analysis_type="overview")

# Step 3: 放大关键区域
for region in bounds["regions"][:3]:  # 前 3 个重要区域
    image = render_drawing_region(
        "building.dxf",
        bbox=region["bbox"],
        output_size=(2048, 2048)
    )

    # AI 分析
    result = analyze_drawing_visual(image["image_path"], analysis_type="annotations")

    # 如果需要进一步放大
    if result.get("needs_zoom"):
        detail = render_drawing_region(
            "building.dxf",
            bbox=result["zoom_area"],
            output_size=(2048, 2048)
        )
```

---

## 🎉 总结

这个方案的核心优势：

1. **智能化**: Agent 可以像人一样分析图纸
2. **高效**: 只渲染需要的部分
3. **灵活**: 可以无限放大查看细节
4. **实用**: 解决了大型图纸的清晰度问题

类似于 Google Maps 的瓦片加载机制，非常适合大型 CAD 图纸的智能分析！
