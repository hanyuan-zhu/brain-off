#!/usr/bin/env python3
"""
区域识别辅助函数

用于智能识别 CAD 图纸中的关键区域
"""

from typing import Dict, List, Set, Tuple, Any


def cluster_grids(
    high_density_grids: Dict[Tuple[int, int], Dict],
    grid_size: int
) -> List[Dict[str, Any]]:
    """
    聚类相邻的高密度网格，形成区域

    Args:
        high_density_grids: 高密度网格字典 {(grid_x, grid_y): {entities, layers}}
        grid_size: 网格大小（mm）

    Returns:
        区域列表
    """
    if not high_density_grids:
        return []

    # 使用并查集算法聚类相邻网格
    visited = set()
    regions = []

    for grid_key in high_density_grids.keys():
        if grid_key in visited:
            continue

        # BFS 查找连通的网格
        cluster = _bfs_cluster(grid_key, high_density_grids, visited)

        if cluster:
            # 计算聚类的边界框
            region = _calculate_cluster_bbox(cluster, high_density_grids, grid_size)
            regions.append(region)

    return regions


def _bfs_cluster(
    start_grid: Tuple[int, int],
    grid_map: Dict[Tuple[int, int], Dict],
    visited: Set[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """
    使用 BFS 查找连通的网格

    Args:
        start_grid: 起始网格坐标
        grid_map: 网格字典
        visited: 已访问的网格集合

    Returns:
        连通的网格列表
    """
    cluster = []
    queue = [start_grid]
    visited.add(start_grid)

    while queue:
        current = queue.pop(0)
        cluster.append(current)

        # 检查 8 个相邻网格
        gx, gy = current
        neighbors = [
            (gx-1, gy-1), (gx, gy-1), (gx+1, gy-1),
            (gx-1, gy),               (gx+1, gy),
            (gx-1, gy+1), (gx, gy+1), (gx+1, gy+1)
        ]

        for neighbor in neighbors:
            if neighbor in grid_map and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return cluster


def _calculate_cluster_bbox(
    cluster: List[Tuple[int, int]],
    grid_map: Dict[Tuple[int, int], Dict],
    grid_size: int
) -> Dict[str, Any]:
    """
    计算聚类的边界框和统计信息

    Args:
        cluster: 网格坐标列表
        grid_map: 网格字典
        grid_size: 网格大小

    Returns:
        区域信息字典
    """
    # 计算网格边界
    grid_xs = [g[0] for g in cluster]
    grid_ys = [g[1] for g in cluster]

    min_grid_x = min(grid_xs)
    max_grid_x = max(grid_xs)
    min_grid_y = min(grid_ys)
    max_grid_y = max(grid_ys)

    # 转换为实际坐标
    min_x = min_grid_x * grid_size
    min_y = min_grid_y * grid_size
    max_x = (max_grid_x + 1) * grid_size
    max_y = (max_grid_y + 1) * grid_size

    # 统计实体和图层
    total_entities = 0
    all_layers = set()

    for grid_key in cluster:
        grid_data = grid_map[grid_key]
        total_entities += len(grid_data['entities'])
        all_layers.update(grid_data['layers'])

    # 计算密度
    area = (max_x - min_x) * (max_y - min_y)
    density = total_entities / area if area > 0 else 0

    # 生成区域名称
    region_name = _generate_region_name(all_layers, total_entities)

    return {
        "name": region_name,
        "bbox": {
            "x": round(min_x, 2),
            "y": round(min_y, 2),
            "width": round(max_x - min_x, 2),
            "height": round(max_y - min_y, 2)
        },
        "entity_count": total_entities,
        "density": round(density, 6),
        "layers": sorted(list(all_layers)),
        "grid_count": len(cluster)
    }


def _generate_region_name(layers: Set[str], entity_count: int) -> str:
    """
    根据图层和实体数量生成区域名称

    Args:
        layers: 图层集合
        entity_count: 实体数量

    Returns:
        区域名称
    """
    # 关键图层映射
    layer_keywords = {
        'WALL': '墙体',
        'COLUMN': '柱子',
        'WINDOW': '门窗',
        'DIM': '标注',
        'TEXT': '文字',
        'AXIS': '轴线'
    }

    # 查找主要图层
    main_layers = []
    for layer in layers:
        layer_upper = layer.upper()
        for keyword, name in layer_keywords.items():
            if keyword in layer_upper:
                main_layers.append(name)
                break

    if main_layers:
        return f"{'/'.join(main_layers[:2])}区域"
    else:
        return f"区域({entity_count}个实体)"
