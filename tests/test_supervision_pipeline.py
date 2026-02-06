import sys
from pathlib import Path

import ezdxf
import matplotlib
import numpy as np
from PIL import Image

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.cad_renderer import get_renderable_bounds, render_drawing_region
from src.services.cad_agent_tools import (
    extract_cad_entities,
    get_cad_metadata,
    inspect_region,
)


MIF_TEXT = (
    "\\M+5B9CC\\M+5B6A8\\M+5B5B2\\M+5D1CC\\M+5B4B9\\M+5B1DA\\M+5A3A8"
    "\\M+5B7C0\\M+5BBF0\\M+5B2BC\\M+5A3A9\\M+5A1A2\\M+5D3E0\\M+5CDAC"
)
MIF_TEXT_DECODED = "\u56fa\u5b9a\u6321\u70df\u5782\u58c1\uff08\u9632\u706b\u5e03\uff09\u3001\u4f59\u540c"


def _make_sample_dxf(path: Path) -> Path:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()

    # Dense local cluster around origin for stable bounds.
    for i in range(30):
        y = 10 * i
        msp.add_line((0, y), (500, y))

    # A line crossing region boundary (tests bbox intersection behavior).
    msp.add_line((-50, 150), (150, 150))

    # Normal text and MIF encoded text.
    text = msp.add_text("测试文字", dxfattribs={"height": 30})
    text.dxf.insert = (120, 220)
    mif = msp.add_text(MIF_TEXT, dxfattribs={"height": 30})
    mif.dxf.insert = (160, 260)

    # Block definition + insert to validate virtual entity handling.
    blk = doc.blocks.new(name="TEST_BLOCK")
    blk.add_line((0, 0), (120, 0))
    blk_text = blk.add_text("BLK", dxfattribs={"height": 20})
    blk_text.dxf.insert = (0, 20)
    msp.add_blockref("TEST_BLOCK", (260, 320))

    # One extreme outlier to test robust bounds filtering.
    msp.add_line((1_000_000_000, 1_000_000_000), (1_000_000_010, 1_000_000_010))

    doc.saveas(path)
    return path


def _non_white_ratio(image_path: str) -> float:
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(image_path) as img:
        arr = np.asarray(img.convert("RGB"))
    return float(np.mean(np.any(arr < 245, axis=2)))


def test_renderable_bounds_filters_outlier(tmp_path):
    dxf_path = _make_sample_dxf(tmp_path / "sample_bounds.dxf")
    result = get_renderable_bounds(str(dxf_path))
    assert result["success"], result

    bounds = result["bounds"]
    assert bounds["max_x"] < 100_000
    assert bounds["max_y"] < 100_000
    assert result["used_entity_count"] < result["raw_entity_count"]


def test_get_cad_metadata_isolated_and_thumbnail_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dxf_path = _make_sample_dxf(tmp_path / "sample_meta.dxf")

    result = get_cad_metadata(str(dxf_path))
    assert result["success"], result

    data = result["data"]
    assert data["bounds_source"] == "renderable_entities"
    assert data["bounds_quality"]["used_entity_count"] <= data["bounds_quality"]["raw_entity_count"]
    assert "thumbnail" in data
    assert Path(data["thumbnail"]).exists()

    with Image.open(data["thumbnail"]) as img:
        assert max(img.size) <= 820


def test_extract_bbox_intersection_captures_crossing_line(tmp_path):
    dxf_path = _make_sample_dxf(tmp_path / "sample_intersection.dxf")
    result = extract_cad_entities(
        file_path=str(dxf_path),
        entity_types=["LINE"],
        bbox={"x": 0, "y": 100, "width": 100, "height": 100},
    )
    assert result["success"], result
    assert result["data"]["total_count"] >= 1


def test_extract_text_decodes_mif_text(tmp_path):
    dxf_path = _make_sample_dxf(tmp_path / "sample_decode.dxf")
    result = extract_cad_entities(
        file_path=str(dxf_path),
        entity_types=["TEXT"],
        bbox={"x": 0, "y": 0, "width": 1000, "height": 1000},
    )
    assert result["success"], result
    texts = [e.get("text", "") for e in result["data"]["entities"]]
    assert any(MIF_TEXT_DECODED in t for t in texts)


def test_inspect_region_and_extract_counts_are_consistent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dxf_path = _make_sample_dxf(tmp_path / "sample_consistency.dxf")
    bbox = {"x": 0, "y": 0, "width": 1000, "height": 1000}

    inspect_result = inspect_region(str(dxf_path), **bbox, output_size=512)
    assert inspect_result["success"], inspect_result

    extract_result = extract_cad_entities(str(dxf_path), bbox=bbox)
    assert extract_result["success"], extract_result

    inspect_count = inspect_result["data"]["entity_summary"]["total_count"]
    extract_count = extract_result["data"]["total_count"]
    assert inspect_count == extract_count

    texts = inspect_result["data"]["key_content"]["texts"]
    assert any(MIF_TEXT_DECODED in t.get("text", "") for t in texts)


def test_render_output_size_is_stable(tmp_path):
    dxf_path = _make_sample_dxf(tmp_path / "sample_render_size.dxf")
    result = render_drawing_region(
        file_path=str(dxf_path),
        bbox={"x": 0, "y": 0, "width": 1000, "height": 500},
        output_size=(400, 400),
        output_path=str(tmp_path / "render.png"),
    )
    assert result["success"], result
    assert result["output_size"] == [400, 200]

    with Image.open(result["image_path"]) as img:
        assert img.size == (400, 200)
    assert _non_white_ratio(result["image_path"]) > 0.002


def test_standalone_render_extract_match_combined_inspect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dxf_path = _make_sample_dxf(tmp_path / "sample_combined_compare.dxf")
    bbox = {"x": 0, "y": 0, "width": 1000, "height": 500}

    standalone_render = render_drawing_region(
        file_path=str(dxf_path),
        bbox=bbox,
        output_size=(512, 512),
        output_path=str(tmp_path / "standalone_render.png"),
    )
    assert standalone_render["success"], standalone_render

    standalone_extract = extract_cad_entities(str(dxf_path), bbox=bbox)
    assert standalone_extract["success"], standalone_extract

    inspect_result = inspect_region(str(dxf_path), **bbox, output_size=512)
    assert inspect_result["success"], inspect_result

    inspect_image = inspect_result["data"]["image_path"]
    assert Path(inspect_image).exists()

    with Image.open(standalone_render["image_path"]) as standalone_img:
        standalone_size = standalone_img.size
    with Image.open(inspect_image) as inspect_img:
        inspect_size = inspect_img.size

    assert standalone_size == inspect_size

    standalone_count = standalone_extract["data"]["total_count"]
    inspect_count = inspect_result["data"]["entity_summary"]["total_count"]
    assert standalone_count == inspect_count

    standalone_non_white = _non_white_ratio(standalone_render["image_path"])
    inspect_non_white = _non_white_ratio(inspect_image)
    assert standalone_non_white > 0.002
    assert abs(standalone_non_white - inspect_non_white) < 0.01


def test_inspect_region_base64_is_opt_in(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dxf_path = _make_sample_dxf(tmp_path / "sample_base64_optin.dxf")
    bbox = {"x": 0, "y": 0, "width": 1000, "height": 500}

    default_result = inspect_region(str(dxf_path), **bbox, output_size=512)
    assert default_result["success"], default_result
    assert default_result["data"]["image_base64"] is None

    base64_result = inspect_region(
        str(dxf_path),
        **bbox,
        output_size=512,
        include_image_base64=True,
    )
    assert base64_result["success"], base64_result
    base64_payload = base64_result["data"]["image_base64"]
    assert isinstance(base64_payload, str)
    assert len(base64_payload) > 1000
    assert len(base64_payload) < 200000
