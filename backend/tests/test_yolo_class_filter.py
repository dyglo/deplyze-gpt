import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yolo_service
import video_processor


COCO_NAMES = {
    0: "person",
    2: "car",
    7: "truck",
    9: "traffic light",
    16: "dog",
}

CITYSCAPES_NAMES = {
    0: "road",
    1: "sidewalk",
    6: "traffic light",
    7: "traffic sign",
    11: "person",
    13: "car",
    18: "bicycle",
}


def patch_models(monkeypatch, names_by_model):
    def fake_get_model(model_type):
        return SimpleNamespace(names=names_by_model[model_type])

    monkeypatch.setattr(yolo_service, "get_model", fake_get_model)


def test_resolve_coco_detection_filter_variants(monkeypatch):
    patch_models(monkeypatch, {"yolo26": COCO_NAMES})

    assert yolo_service.resolve_class_filter("detect only the cars", "yolo26").ids == [2]
    assert yolo_service.resolve_class_filter("person and dog", "yolo26").ids == [0, 16]
    assert yolo_service.resolve_class_filter("find the traffic lights", "yolo26").ids == [9]
    assert yolo_service.resolve_class_filter("detect only cars, trucks or van", "yolo26").ids == [2, 7]
    assert yolo_service.resolve_class_filter("detect all objects", "yolo26") is None
    assert yolo_service.resolve_class_filter("describe this image in detail", "yolo26") is None


def test_resolve_coco_instance_segmentation_uses_same_vocabulary(monkeypatch):
    patch_models(monkeypatch, {"yolo26-seg": COCO_NAMES})

    class_filter = yolo_service.resolve_class_filter(
        "segment only the person and the dog",
        "yolo26-seg",
    )

    assert class_filter.ids == [0, 16]
    assert class_filter.names == ["person", "dog"]


def test_resolve_cityscapes_semantic_filter_variants(monkeypatch):
    patch_models(monkeypatch, {"yolo26-sem": CITYSCAPES_NAMES})

    assert yolo_service.resolve_class_filter("segment only road and cars", "yolo26-sem").ids == [0, 13]
    assert yolo_service.resolve_class_filter("show traffic signs", "yolo26-sem").ids == [7]
    assert yolo_service.resolve_class_filter("count people visible", "yolo26-sem").ids == [11]
    assert yolo_service.resolve_class_filter("Perform semantic segmentation on person", "yolo26-sem").ids == [11]


def test_invalid_filter_mentions_available_classes(monkeypatch):
    patch_models(monkeypatch, {"yolo26-sem": CITYSCAPES_NAMES, "yolo26": COCO_NAMES})

    with pytest.raises(yolo_service.ClassFilterError) as semantic_error:
        yolo_service.resolve_class_filter("segment only dog", "yolo26-sem")
    assert "dog" in str(semantic_error.value)
    assert "Try one of the supported classes" in str(semantic_error.value)

    with pytest.raises(yolo_service.ClassFilterError) as partial_error:
        yolo_service.resolve_class_filter("cars and unicorn", "yolo26")
    assert "unicorn" in str(partial_error.value)
    assert "car" in str(partial_error.value)
    assert "Available classes for" not in str(partial_error.value)


def test_analyze_image_yolo_passes_classes_only_when_filtered(monkeypatch):
    calls = []

    class FakeModel:
        names = COCO_NAMES

        def predict(self, source, **kwargs):
            calls.append((source, kwargs))
            result = SimpleNamespace(names=self.names, boxes=None, semantic_mask=None)
            return [result]

    monkeypatch.setattr(yolo_service, "get_model", lambda _model_type: FakeModel())
    monkeypatch.setattr(
        yolo_service,
        "render_clean_annotations",
        lambda _result, base_image=None, class_filter_ids=None: np.zeros((4, 4, 3), dtype=np.uint8),
    )

    yolo_service.analyze_image_yolo("image.jpg", "yolo26", 0.4, [2])
    assert calls[-1][0] == "image.jpg"
    assert calls[-1][1]["conf"] == 0.4
    assert calls[-1][1]["classes"] == [2]

    yolo_service.analyze_image_yolo("image.jpg", "yolo26", 0.25)
    assert "classes" not in calls[-1][1]


class ArrayLike:
    def __init__(self, value):
        self.value = value

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def test_semantic_helpers_filter_unselected_classes():
    class_map = np.full((100, 100), 13, dtype=np.uint8)
    class_map[95:, 95:] = 0
    base_image = np.zeros((100, 100, 3), dtype=np.uint8)
    result = SimpleNamespace(
        names=CITYSCAPES_NAMES,
        orig_img=base_image,
        semantic_mask=SimpleNamespace(data=ArrayLike(class_map)),
    )

    classes = yolo_service.extract_semantic_classes(result, class_filter_ids=[13])
    assert classes == [{"class": "car", "coverage": 0.9975}]

    rendered = yolo_service.render_clean_annotations(result, base_image, class_filter_ids=[13])
    assert np.array_equal(rendered[99, 99], base_image[99, 99])
    assert not np.array_equal(rendered[50, 50], base_image[50, 50])


def test_video_predict_kwargs_use_quality_settings():
    filtered_instance = video_processor._video_predict_kwargs("yolo26-seg", 0.25, [2, 7])
    assert filtered_instance["classes"] == [2, 7]
    assert filtered_instance["conf"] == video_processor.FILTERED_VIDEO_CONFIDENCE
    assert filtered_instance["imgsz"] == video_processor.INSTANCE_VIDEO_IMGSZ
    assert filtered_instance["retina_masks"] is True
    assert filtered_instance["agnostic_nms"] is True

    unfiltered_detection = video_processor._video_predict_kwargs("yolo26", 0.25)
    assert unfiltered_detection["conf"] == 0.25
    assert unfiltered_detection["imgsz"] == video_processor.DETECTION_VIDEO_IMGSZ
    assert "classes" not in unfiltered_detection
    assert "agnostic_nms" not in unfiltered_detection

    filtered_semantic = video_processor._video_predict_kwargs("yolo26-sem", 0.25, [11])
    assert filtered_semantic["classes"] == [11]
    assert filtered_semantic["imgsz"] == video_processor.SEMANTIC_IMGSZ
    assert "conf" not in filtered_semantic
