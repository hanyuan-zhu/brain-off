#!/usr/bin/env python3
"""
Batch validation for supervision skill image/data pipeline.

Checks per file:
1) get_cad_metadata success and valid bounds
2) standalone render is valid and not almost blank
3) standalone extract succeeds
4) inspect_region renders image with stable size
5) standalone extract count matches inspect_region summary
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.cad_agent_tools import (  # noqa: E402
    extract_cad_entities,
    get_cad_metadata,
    inspect_region,
)
from src.services.cad_renderer import render_drawing_region  # noqa: E402


def image_non_white_ratio(image_path: str) -> float:
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    mask = np.any(rgb < 245, axis=2)
    return float(mask.mean())


def validate_file(file_path: Path, output_size: int, min_non_white: float) -> Dict:
    report = {
        "file": str(file_path),
        "checks": {},
        "pass": False,
    }

    meta = get_cad_metadata(str(file_path))
    if not meta.get("success"):
        report["checks"]["metadata"] = {"pass": False, "error": meta.get("error")}
        return report

    bounds = meta.get("data", {}).get("bounds")
    bounds_ok = (
        isinstance(bounds, dict)
        and bounds.get("width", 0) > 0
        and bounds.get("height", 0) > 0
    )
    report["checks"]["metadata"] = {
        "pass": bounds_ok,
        "bounds": bounds,
        "bounds_source": meta.get("data", {}).get("bounds_source"),
    }
    if not bounds_ok:
        return report

    bbox = {
        "x": bounds["min_x"],
        "y": bounds["min_y"],
        "width": bounds["width"],
        "height": bounds["height"],
    }

    # 1) Standalone render check (no extraction involved).
    render_only = render_drawing_region(
        file_path=str(file_path),
        bbox=bbox,
        output_size=(output_size, output_size),
    )
    if not render_only.get("success"):
        report["checks"]["render_only"] = {"pass": False, "error": render_only.get("error")}
        return report

    render_image_path = render_only["image_path"]
    render_image_exists = Path(render_image_path).exists()
    if render_image_exists:
        with Image.open(render_image_path) as img:
            render_image_size = [img.width, img.height]
    else:
        render_image_size = [0, 0]

    render_non_white = image_non_white_ratio(render_image_path) if render_image_exists else 0.0
    render_size_ok = render_image_exists and max(render_image_size) <= output_size and min(render_image_size) > 0
    render_non_blank_ok = render_non_white >= min_non_white
    report["checks"]["render_only"] = {
        "pass": render_size_ok and render_non_blank_ok,
        "image_path": render_image_path,
        "image_size": render_image_size,
        "non_white_ratio": round(render_non_white, 6),
        "image_size_ok": render_size_ok,
        "non_blank_ok": render_non_blank_ok,
    }

    # 2) Standalone extraction check (no rendering involved).
    extract = extract_cad_entities(str(file_path), bbox=bbox)
    if not extract.get("success"):
        report["checks"]["extract_only"] = {"pass": False, "error": extract.get("error")}
        return report
    report["checks"]["extract_only"] = {
        "pass": True,
        "extract_total": extract["data"]["total_count"],
        "entity_count": extract["data"].get("entity_count", {}),
    }

    # 3) Combined tool check (render + extraction in one call).
    inspect = inspect_region(
        file_path=str(file_path),
        x=bounds["min_x"],
        y=bounds["min_y"],
        width=bounds["width"],
        height=bounds["height"],
        output_size=output_size,
    )
    if not inspect.get("success"):
        report["checks"]["inspect_region"] = {"pass": False, "error": inspect.get("error")}
        return report

    inspect_image_path = inspect["data"]["image_path"]
    inspect_image_exists = Path(inspect_image_path).exists()
    if inspect_image_exists:
        with Image.open(inspect_image_path) as img:
            inspect_image_size = [img.width, img.height]
    else:
        inspect_image_size = [0, 0]

    inspect_non_white = image_non_white_ratio(inspect_image_path) if inspect_image_exists else 0.0
    inspect_size_ok = (
        inspect_image_exists
        and max(inspect_image_size) <= output_size
        and min(inspect_image_size) > 0
    )
    inspect_non_blank_ok = inspect_non_white >= min_non_white

    report["checks"]["inspect_region"] = {
        "pass": inspect_size_ok and inspect_non_blank_ok,
        "image_path": inspect_image_path,
        "image_size": inspect_image_size,
        "non_white_ratio": round(inspect_non_white, 6),
        "image_size_ok": inspect_size_ok,
        "non_blank_ok": inspect_non_blank_ok,
        "entity_total_in_inspect": inspect["data"]["entity_summary"]["total_count"],
        "text_count_in_inspect": inspect["data"]["key_content"]["text_count"],
    }

    # 4) Consistency check between standalone extraction and combined tool.
    inspect_count = inspect["data"]["entity_summary"]["total_count"]
    extract_count = extract["data"]["total_count"]
    count_match = inspect_count == extract_count
    report["checks"]["inspect_extract_consistency"] = {
        "pass": count_match,
        "inspect_total": inspect_count,
        "extract_total": extract_count,
        "delta": inspect_count - extract_count,
    }

    report["pass"] = all(item.get("pass") for item in report["checks"].values())
    return report


def discover_dxf_files(root: Path, limit: int) -> List[Path]:
    files = sorted(p for p in root.rglob("*.dxf") if p.is_file())
    return files[:limit] if limit > 0 else files


def main():
    parser = argparse.ArgumentParser(description="Batch test supervision image pipeline")
    parser.add_argument(
        "--root",
        default="workspace/cad_files",
        help="Root directory to discover DXF files",
    )
    parser.add_argument("--limit", type=int, default=6, help="Max number of DXF files to test")
    parser.add_argument("--size", type=int, default=900, help="inspect_region output_size")
    parser.add_argument("--min-non-white", type=float, default=0.002, help="Minimum non-white pixel ratio")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"Root path does not exist: {root}")
        return 1

    files = discover_dxf_files(root, args.limit)
    if not files:
        print(f"No DXF files found under: {root}")
        return 1

    print(f"Testing {len(files)} DXF files...")
    reports = []
    for idx, file_path in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] {file_path}")
        reports.append(validate_file(file_path, output_size=args.size, min_non_white=args.min_non_white))

    passed = sum(1 for r in reports if r["pass"])
    summary = {
        "tested_files": len(reports),
        "passed_files": passed,
        "failed_files": len(reports) - passed,
        "pass_rate": round(passed / len(reports), 4),
    }

    output_dir = Path("workspace/rendered/diagnostics")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"supervision_batch_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(
        json.dumps({"summary": summary, "reports": reports}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nSummary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {output_path}")

    return 0 if summary["failed_files"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
