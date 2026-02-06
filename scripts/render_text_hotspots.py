#!/usr/bin/env python3
"""
Render zoomed text hotspots for a DXF file and generate a markdown preview.
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import ezdxf
from ezdxf.tools.text import plain_mtext

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.cad_agent_tools import get_cad_metadata
from src.services.cad_renderer import decode_cad_text, render_drawing_region


def iter_entities(msp) -> Iterable:
    for entity in msp:
        if entity.dxftype() == "INSERT":
            try:
                for sub_entity in entity.virtual_entities():
                    yield sub_entity
            except Exception:
                pass
        yield entity


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def collect_text_points(file_path: str) -> List[Dict]:
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    points: List[Dict] = []
    for entity in iter_entities(msp):
        entity_type = entity.dxftype()
        if entity_type not in ("TEXT", "MTEXT"):
            continue

        try:
            x = float(entity.dxf.insert.x)
            y = float(entity.dxf.insert.y)
        except Exception:
            continue

        try:
            if entity_type == "TEXT":
                raw = entity.dxf.text
            else:
                raw = plain_mtext(entity.text)
            text = decode_cad_text(raw).replace("\x00", "").strip()
        except Exception:
            text = ""

        if not text:
            continue

        points.append(
            {
                "x": x,
                "y": y,
                "text": text,
            }
        )

    return points


def pick_hotspot_centers(
    text_points: List[Dict],
    bounds: Dict[str, float],
    max_regions: int,
) -> List[Tuple[float, float, int]]:
    min_x, min_y = bounds["min_x"], bounds["min_y"]
    width, height = bounds["width"], bounds["height"]

    cell_w = max(width / 30.0, 2000.0)
    cell_h = max(height / 20.0, 2000.0)

    grid = defaultdict(list)
    for idx, p in enumerate(text_points):
        gx = int((p["x"] - min_x) // cell_w)
        gy = int((p["y"] - min_y) // cell_h)
        grid[(gx, gy)].append(idx)

    ranked = sorted(
        (
            (len(idxs), gx, gy, idxs)
            for (gx, gy), idxs in grid.items()
        ),
        reverse=True,
    )

    selected: List[Tuple[float, float, int]] = []
    min_dist = max(cell_w, cell_h) * 1.8
    for count, gx, gy, _idxs in ranked:
        cx = min_x + (gx + 0.5) * cell_w
        cy = min_y + (gy + 0.5) * cell_h

        keep = True
        for sx, sy, _ in selected:
            if math.hypot(cx - sx, cy - sy) < min_dist:
                keep = False
                break
        if not keep:
            continue

        selected.append((cx, cy, count))
        if len(selected) >= max_regions:
            break

    if not selected and text_points:
        # Fallback to one central text point when density grouping fails.
        p = text_points[len(text_points) // 2]
        selected.append((p["x"], p["y"], 1))

    return selected


def make_zoom_bbox(
    center_x: float,
    center_y: float,
    bounds: Dict[str, float],
    zoom_scale: float,
) -> Dict[str, float]:
    min_x, min_y = bounds["min_x"], bounds["min_y"]
    max_x, max_y = bounds["max_x"], bounds["max_y"]
    full_w, full_h = bounds["width"], bounds["height"]

    zoom_w = max(full_w * zoom_scale, 12000.0)
    zoom_h = max(full_h * zoom_scale, 12000.0)
    zoom_w = min(zoom_w, full_w)
    zoom_h = min(zoom_h, full_h)

    x = center_x - zoom_w / 2.0
    y = center_y - zoom_h / 2.0
    x = clamp(x, min_x, max_x - zoom_w)
    y = clamp(y, min_y, max_y - zoom_h)

    return {"x": round(x, 2), "y": round(y, 2), "width": round(zoom_w, 2), "height": round(zoom_h, 2)}


def sample_texts_in_bbox(text_points: List[Dict], bbox: Dict[str, float], limit: int = 8) -> List[str]:
    x1, y1 = bbox["x"], bbox["y"]
    x2, y2 = x1 + bbox["width"], y1 + bbox["height"]

    hits = []
    for p in text_points:
        if x1 <= p["x"] <= x2 and y1 <= p["y"] <= y2:
            text = p["text"].replace("\n", " ").strip()
            if text:
                hits.append(text)

    seen = set()
    unique = []
    for text in hits:
        if text in seen:
            continue
        seen.add(text)
        unique.append(text[:80])
        if len(unique) >= limit:
            break
    return unique


def render_hotspots(
    file_path: str,
    output_size: int,
    max_regions: int,
    zoom_scale: float,
) -> Dict:
    meta = get_cad_metadata(file_path)
    if not meta.get("success"):
        return {"success": False, "error": meta.get("error", "metadata failed")}

    bounds = meta.get("data", {}).get("bounds")
    if not bounds:
        return {"success": False, "error": "No bounds from metadata"}

    text_points = collect_text_points(file_path)
    if not text_points:
        return {"success": False, "error": "No decoded TEXT/MTEXT found"}

    centers = pick_hotspot_centers(text_points, bounds, max_regions=max_regions)
    if not centers:
        return {"success": False, "error": "No text hotspots selected"}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("workspace/rendered/hotspots")
    output_dir.mkdir(parents=True, exist_ok=True)

    hotspot_reports = []
    for i, (cx, cy, count) in enumerate(centers, 1):
        bbox = make_zoom_bbox(cx, cy, bounds, zoom_scale=zoom_scale)
        image_path = output_dir / f"text_hotspot_{Path(file_path).stem}_{timestamp}_{i}.png"
        render = render_drawing_region(
            file_path=file_path,
            bbox=bbox,
            output_size=(output_size, output_size),
            output_path=str(image_path),
            color_mode="by_layer",
        )
        if not render.get("success"):
            hotspot_reports.append(
                {
                    "index": i,
                    "success": False,
                    "error": render.get("error", "render failed"),
                    "bbox": bbox,
                    "text_count_estimate": count,
                }
            )
            continue

        hotspot_reports.append(
            {
                "index": i,
                "success": True,
                "bbox": bbox,
                "center": {"x": round(cx, 2), "y": round(cy, 2)},
                "text_count_estimate": count,
                "image_path": render.get("image_path"),
                "output_size": render.get("output_size"),
                "sample_texts": sample_texts_in_bbox(text_points, bbox, limit=10),
            }
        )

    return {
        "success": True,
        "file_path": file_path,
        "bounds": bounds,
        "text_points_count": len(text_points),
        "hotspots": hotspot_reports,
        "parameters": {
            "output_size": output_size,
            "max_regions": max_regions,
            "zoom_scale": zoom_scale,
        },
    }


def write_markdown(report: Dict, md_path: Path):
    lines: List[str] = []
    lines.append("# Text Hotspot Zoom Report")
    lines.append("")
    lines.append(f"- DXF: `{report['file_path']}`")
    lines.append(f"- Total decoded text points: `{report['text_points_count']}`")
    lines.append(f"- Output size: `{report['parameters']['output_size']}`")
    lines.append(f"- Max regions: `{report['parameters']['max_regions']}`")
    lines.append(f"- Zoom scale: `{report['parameters']['zoom_scale']}`")
    lines.append("")

    lines.append("## Hotspots")
    lines.append("")

    for item in report["hotspots"]:
        lines.append(f"### Region {item['index']}")
        lines.append("")
        if not item.get("success"):
            lines.append(f"- Status: FAIL")
            lines.append(f"- Error: `{item.get('error', 'unknown')}`")
            lines.append(f"- BBox: `{item.get('bbox')}`")
            lines.append("")
            continue

        lines.append("- Status: OK")
        lines.append(f"- BBox: `{item['bbox']}`")
        lines.append(f"- Center: `{item['center']}`")
        lines.append(f"- Estimated text count in grid: `{item['text_count_estimate']}`")
        lines.append(f"- Rendered size: `{item['output_size']}`")
        lines.append(f"- Image: `{item['image_path']}`")
        lines.append("")

        image_path = Path(item["image_path"])
        rel_str = os.path.relpath(image_path, md_path.parent).replace("\\", "/")
        lines.append(f"![Region {item['index']}]({rel_str})")
        lines.append("")

        sample_texts = item.get("sample_texts", [])
        if sample_texts:
            lines.append("Sample texts:")
            for text in sample_texts:
                lines.append(f"- `{text}`")
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Render text hotspots and generate markdown report")
    parser.add_argument("--file", required=True, help="DXF file path")
    parser.add_argument("--size", type=int, default=2400, help="max side length for each hotspot image")
    parser.add_argument("--regions", type=int, default=4, help="number of hotspot regions")
    parser.add_argument("--zoom-scale", type=float, default=0.16, help="zoom bbox size as ratio of full bounds")
    args = parser.parse_args()

    report = render_hotspots(
        file_path=args.file,
        output_size=args.size,
        max_regions=args.regions,
        zoom_scale=args.zoom_scale,
    )
    if not report.get("success"):
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    out_dir = Path("workspace/rendered/diagnostics")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(args.file).stem
    json_path = out_dir / f"text_hotspot_report_{stem}_{timestamp}.json"
    md_path = out_dir / f"text_hotspot_report_{stem}_{timestamp}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
