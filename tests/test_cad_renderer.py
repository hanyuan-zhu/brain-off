import matplotlib

matplotlib.use("Agg")

import sys
from pathlib import Path

import ezdxf
import matplotlib.image as mpimg
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.cad_renderer import decode_cad_text, render_drawing_region


def _image_non_white_ratio(image_path):
    image = mpimg.imread(image_path)
    rgb = image[:, :, :3]
    return float(np.mean(np.any(rgb < 0.98, axis=2)))


def test_line_crossing_bbox_is_rendered(tmp_path):
    dxf_path = tmp_path / "line_crossing.dxf"
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_line((-50, 50), (150, 50))
    doc.saveas(dxf_path)

    result = render_drawing_region(
        file_path=str(dxf_path),
        bbox={"x": 0, "y": 0, "width": 100, "height": 100},
        output_size=(200, 200),
        output_path=str(tmp_path / "line_crossing.png"),
    )

    assert result["success"], result
    non_white_ratio = _image_non_white_ratio(result["image_path"])
    assert non_white_ratio > 0.001


def test_rendered_image_size_is_stable_with_large_text(tmp_path):
    dxf_path = tmp_path / "large_text.dxf"
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    text = msp.add_text("A", dxfattribs={"height": 5000})
    text.dxf.insert = (50, 50)
    doc.saveas(dxf_path)

    result = render_drawing_region(
        file_path=str(dxf_path),
        bbox={"x": 0, "y": 0, "width": 100, "height": 100},
        output_size=(300, 300),
        output_path=str(tmp_path / "large_text.png"),
    )

    assert result["success"], result
    image = mpimg.imread(result["image_path"])
    assert image.shape[0] <= 320
    assert image.shape[1] <= 320


def test_decode_mif_encoded_text():
    encoded = (
        "\\M+5B9CC\\M+5B6A8\\M+5B5B2\\M+5D1CC\\M+5B4B9\\M+5B1DA\\M+5A3A8"
        "\\M+5B7C0\\M+5BBF0\\M+5B2BC\\M+5A3A9\\M+5A1A2\\M+5D3E0\\M+5CDAC"
    )
    decoded = decode_cad_text(encoded)
    assert decoded == "\u56fa\u5b9a\u6321\u70df\u5782\u58c1\uff08\u9632\u706b\u5e03\uff09\u3001\u4f59\u540c"
