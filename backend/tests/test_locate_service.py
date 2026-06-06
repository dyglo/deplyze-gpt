import base64
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locate_service


def test_parse_locate_output_scales_and_clamps_boxes_and_points():
    detections = locate_service.parse_locate_output(
        "red shirt <box><100><200><900><1100></box> signal <box><500><250></box>",
        image_width=200,
        image_height=100,
        label="target",
    )

    assert detections == [
        {"kind": "box", "class": "target", "bbox": [20.0, 20.0, 180.0, 100.0]},
        {"kind": "point", "class": "target", "point": [100.0, 25.0]},
    ]


def test_parse_locate_output_supports_comma_format_and_ignores_invalid_boxes():
    detections = locate_service.parse_locate_output(
        "<box>100, 100, 100, 200</box> <box>250, 500</box> <box>0, 0, 1000, 1000</box>",
        image_width=80,
        image_height=40,
        label="layout",
    )

    assert detections == [
        {"kind": "box", "class": "layout", "bbox": [0.0, 0.0, 80.0, 40.0]},
        {"kind": "point", "class": "layout", "point": [20.0, 20.0]},
    ]


def test_render_locate_annotations_changes_pixels_for_box_and_point():
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    detections = [
        {"kind": "box", "class": "object", "bbox": [10.0, 20.0, 70.0, 90.0]},
        {"kind": "point", "class": "target", "point": [120.0, 60.0]},
    ]

    rendered = locate_service.render_locate_annotations(image, detections)

    assert rendered.shape == image.shape
    assert not np.array_equal(rendered, image)
    assert not np.array_equal(rendered[20, 10], image[20, 10])
    assert not np.array_equal(rendered[60, 120], image[60, 120])


def test_analyze_image_locate_returns_existing_image_result_shape(monkeypatch, tmp_path):
    image_path = tmp_path / "input.jpg"
    cv2.imwrite(str(image_path), np.zeros((100, 200, 3), dtype=np.uint8))

    monkeypatch.setattr(
        locate_service,
        "_call_locate_endpoint",
        lambda **_kwargs: {"answer": "<box><100><200><900><800></box>"},
    )

    result = locate_service.analyze_image_locate(str(image_path), "people wearing red shirts")

    assert result["type"] == "image"
    assert result["content"].startswith("data:image/jpeg;base64,")
    assert result["detections"] == [
        {"kind": "box", "class": "people wearing red shirts", "bbox": [20.0, 20.0, 180.0, 80.0]}
    ]
    encoded = result["content"].split(",", 1)[1]
    assert base64.b64decode(encoded)
