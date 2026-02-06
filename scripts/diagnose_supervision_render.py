#!/usr/bin/env python3
"""
Render/data alignment diagnostic for supervision skill.

Usage:
  python scripts/diagnose_supervision_render.py --file workspace/cad_files/a.dxf
  python scripts/diagnose_supervision_render.py --file a.dxf --x 0 --y 0 --width 10000 --height 8000
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.cad_renderer import render_drawing_region
from src.services.cad_agent_tools import extract_cad_entities, get_cad_metadata


def image_non_white_ratio(image_path: str) -> float:
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    mask = np.any(rgb < 245, axis=2)
    return float(mask.mean())


def main():
    parser = argparse.ArgumentParser(description="Diagnose CAD render/data sync")
    parser.add_argument("--file", required=True, help="DXF file path")
    parser.add_argument("--x", type=float, default=None)
    parser.add_argument("--y", type=float, default=None)
    parser.add_argument("--width", type=float, default=None)
    parser.add_argument("--height", type=float, default=None)
    parser.add_argument("--size", type=int, default=1200, help="max image side in px")
    args = parser.parse_args()

    meta = get_cad_metadata(args.file)
    if not meta.get("success"):
        print(json.dumps({"success": False, "stage": "metadata", "error": meta.get("error")}, ensure_ascii=False, indent=2))
        return 1

    bounds = meta["data"].get("bounds")
    if not bounds:
        print(json.dumps({"success": False, "stage": "metadata", "error": "No bounds available"}, ensure_ascii=False, indent=2))
        return 1

    bbox = {
        "x": args.x if args.x is not None else bounds["min_x"],
        "y": args.y if args.y is not None else bounds["min_y"],
        "width": args.width if args.width is not None else bounds["width"],
        "height": args.height if args.height is not None else bounds["height"],
    }

    render = render_drawing_region(
        file_path=args.file,
        bbox=bbox,
        output_size=(args.size, args.size),
        color_mode="by_layer",
    )
    if not render.get("success"):
        print(json.dumps({"success": False, "stage": "render", "error": render.get("error")}, ensure_ascii=False, indent=2))
        return 1

    entities = extract_cad_entities(
        file_path=args.file,
        bbox=bbox,
    )
    if not entities.get("success"):
        print(json.dumps({"success": False, "stage": "extract", "error": entities.get("error")}, ensure_ascii=False, indent=2))
        return 1

    image_path = render["image_path"]
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(image_path) as image:
        image_size = {"width": image.width, "height": image.height}

    text_entities = extract_cad_entities(
        file_path=args.file,
        entity_types=["TEXT", "MTEXT"],
        bbox=bbox,
    )
    sample_texts = []
    if text_entities.get("success"):
        for item in text_entities["data"]["entities"]:
            if item.get("text"):
                sample_texts.append(item["text"])
            if len(sample_texts) >= 10:
                break

    report = {
        "success": True,
        "file": args.file,
        "bbox": bbox,
        "metadata_bounds": bounds,
        "render": {
            "image_path": image_path,
            "output_size_reported": render.get("output_size"),
            "image_size_actual": image_size,
            "scale": render.get("scale"),
            "non_white_ratio": round(image_non_white_ratio(image_path), 6),
        },
        "extract": {
            "total_count": entities["data"]["total_count"],
            "entity_count": entities["data"]["entity_count"],
            "sample_texts": sample_texts,
        },
    }

    output_dir = Path("workspace/rendered/diagnostics")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"diagnosis_{Path(args.file).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved report: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
