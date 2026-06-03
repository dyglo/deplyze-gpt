import cv2
import base64
import logging
import numpy as np
import os
import shutil
from pathlib import Path
from ultralytics import YOLO

logger = logging.getLogger(__name__)

_models: dict = {}

MODEL_MAP = {
    'yolo26': 'yolo26n.pt',
    'yolo26-seg': 'yolo26n-seg.pt',
    'yolo26-sem': 'yolo26n-sem.pt',
}

ANNOTATION_PALETTE = [
    (70, 156, 255),
    (92, 213, 160),
    (255, 178, 83),
    (238, 130, 238),
    (86, 205, 230),
    (144, 132, 255),
    (116, 196, 118),
    (250, 125, 129),
]
SEMANTIC_FILL_ALPHA = 0.62
SEMANTIC_BOUNDARY_ALPHA = 0.72
INSTANCE_MASK_ALPHA = 0.58
INSTANCE_BOUNDARY_ALPHA = 0.85


def get_model_path(model_type: str) -> Path:
    model_name = MODEL_MAP.get(model_type, 'yolo26n.pt')
    return Path(__file__).parent / model_name


def ensure_model_available(model_type: str) -> Path:
    model_name = MODEL_MAP.get(model_type, 'yolo26n.pt')
    model_path = get_model_path(model_type)
    if model_path.exists():
        return model_path

    previous_cwd = Path.cwd()
    try:
        os.chdir(Path(__file__).parent)
        YOLO(model_name)
    finally:
        os.chdir(previous_cwd)

    downloaded = Path(__file__).parent / model_name
    if not downloaded.exists():
        cache_candidate = Path.home() / ".cache" / "ultralytics" / model_name
        if cache_candidate.exists():
            shutil.copy2(cache_candidate, model_path)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file '{model_name}' not found and automatic download failed."
        )

    return model_path


def get_model(model_type: str) -> YOLO:
    if model_type not in _models:
        model_path = ensure_model_available(model_type)
        model_name = model_path.name
        logger.info(f"Loading YOLO model: {model_name}")
        _models[model_type] = YOLO(str(model_path))
        logger.info(f"YOLO model {model_name} ready")
    return _models[model_type]


def _annotation_color(cls_id: int) -> tuple:
    color = ANNOTATION_PALETTE[cls_id % len(ANNOTATION_PALETTE)]
    return int(color[0]), int(color[1]), int(color[2])


def _apply_masks(image, result):
    masks = getattr(result, 'masks', None)
    if masks is None or getattr(masks, 'data', None) is None:
        return image

    height, width = image.shape[:2]
    mask_data = masks.data.detach().cpu().numpy()
    classes = []
    if getattr(result, 'boxes', None) is not None and result.boxes.cls is not None:
        classes = [int(cls.item()) for cls in result.boxes.cls]

    for index, mask in enumerate(mask_data):
        cls_id = classes[index] if index < len(classes) else index
        color = np.array(_annotation_color(cls_id), dtype=np.float32)
        resized = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
        mask_area = resized > 0.5
        image[mask_area] = (
            (1.0 - INSTANCE_MASK_ALPHA) * image[mask_area] + INSTANCE_MASK_ALPHA * color
        ).astype(np.uint8)

        contours, _ = cv2.findContours(
            (mask_area.astype(np.uint8) * 255),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if contours:
            boundary_layer = image.copy()
            cv2.drawContours(boundary_layer, contours, -1, tuple(int(c) for c in color), 2, cv2.LINE_AA)
            cv2.addWeighted(boundary_layer, INSTANCE_BOUNDARY_ALPHA, image, 1.0 - INSTANCE_BOUNDARY_ALPHA, 0, image)

    return image


def _render_semantic_annotations(result, base_image=None):
    image = base_image.copy() if base_image is not None else result.orig_img.copy()
    semantic_mask = getattr(result, 'semantic_mask', None)
    if semantic_mask is None or getattr(semantic_mask, 'data', None) is None:
        return image

    class_map = semantic_mask.data.detach().cpu().numpy()
    height, width = image.shape[:2]
    if class_map.shape[:2] != (height, width):
        class_map = cv2.resize(class_map, (width, height), interpolation=cv2.INTER_NEAREST)

    overlay = image.copy()
    ids, counts = np.unique(class_map, return_counts=True)
    valid = [(int(cls_id), int(count)) for cls_id, count in zip(ids, counts) if int(cls_id) != 255]

    for cls_id, _ in valid:
        color = np.array(_annotation_color(cls_id), dtype=np.float32)
        mask = class_map == cls_id
        overlay[mask] = (
            (1.0 - SEMANTIC_FILL_ALPHA) * image[mask] + SEMANTIC_FILL_ALPHA * color
        ).astype(np.uint8)

    image = overlay
    _draw_semantic_boundaries(image, class_map)
    _draw_semantic_legend(image, result.names, valid, width, height)
    return image


def _draw_semantic_boundaries(image, class_map):
    horizontal = np.zeros(class_map.shape, dtype=np.uint8)
    vertical = np.zeros(class_map.shape, dtype=np.uint8)
    horizontal[1:, :] = class_map[1:, :] != class_map[:-1, :]
    vertical[:, 1:] = class_map[:, 1:] != class_map[:, :-1]
    edges = cv2.dilate(
        ((horizontal | vertical) * 255).astype(np.uint8),
        np.ones((2, 2), dtype=np.uint8),
        iterations=1,
    )
    if edges.any():
        boundary_layer = image.copy()
        boundary_layer[edges > 0] = (245, 247, 250)
        cv2.addWeighted(boundary_layer, SEMANTIC_BOUNDARY_ALPHA, image, 1.0 - SEMANTIC_BOUNDARY_ALPHA, 0, image)


def _draw_semantic_legend(image, names: dict, class_counts: list, width: int, height: int):
    if not class_counts:
        return

    total = max(1, width * height)
    top_classes = sorted(class_counts, key=lambda item: item[1], reverse=True)[:6]
    font_scale = max(0.42, min(0.58, width / 1800))
    font_thickness = 1
    row_h = 22
    pad = 9
    swatch = 10

    labels = [
        (cls_id, names.get(cls_id, f"class_{cls_id}"), count / total)
        for cls_id, count in top_classes
    ]
    text_width = 0
    for _, name, ratio in labels:
        text = f"{name} {ratio:.0%}"
        (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        text_width = max(text_width, tw)

    box_w = min(width - 24, max(170, text_width + 42))
    box_h = pad * 2 + row_h * len(labels)
    x1, y1 = 12, 12
    x2, y2 = x1 + box_w, min(height - 12, y1 + box_h)

    panel = image.copy()
    cv2.rectangle(panel, (x1, y1), (x2, y2), (18, 20, 24), -1, cv2.LINE_AA)
    cv2.addWeighted(panel, 0.62, image, 0.38, 0, image)

    for idx, (cls_id, name, ratio) in enumerate(labels):
        y = y1 + pad + (idx * row_h) + 14
        color = _annotation_color(cls_id)
        cv2.rectangle(
            image,
            (x1 + pad, y - swatch),
            (x1 + pad + swatch, y),
            color,
            -1,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            f"{name} {ratio:.0%}",
            (x1 + pad + swatch + 9, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (245, 247, 250),
            font_thickness,
            cv2.LINE_AA,
        )


def render_clean_annotations(result, base_image=None):
    if getattr(result, 'semantic_mask', None) is not None:
        return _render_semantic_annotations(result, base_image)

    image = base_image.copy() if base_image is not None else result.orig_img.copy()
    image = _apply_masks(image, result)
    boxes = getattr(result, 'boxes', None)
    if boxes is None or len(boxes) == 0:
        return image

    height, width = image.shape[:2]
    box_thickness = max(1, min(2, round(min(width, height) / 480)))
    font_scale = max(0.42, min(0.68, width / 1800))
    font_thickness = 1
    pad_x = 6
    pad_y = 4

    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        conf = float(boxes.conf[i].item())
        x1, y1, x2, y2 = [int(round(v)) for v in boxes.xyxy[i].tolist()]
        class_name = result.names.get(cls_id, f"class_{cls_id}")
        label = f"{class_name} {conf:.2f}"
        color = _annotation_color(cls_id)

        cv2.rectangle(image, (x1, y1), (x2, y2), color, box_thickness, cv2.LINE_AA)

        (label_w, label_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )
        label_x1 = max(0, min(x1, width - label_w - (pad_x * 2)))
        label_total_h = label_h + (pad_y * 2) + baseline
        label_y1 = max(0, y1 - label_total_h)
        label_y2 = min(height, label_y1 + label_total_h)

        label_overlay = image.copy()
        cv2.rectangle(
            label_overlay,
            (label_x1, label_y1),
            (label_x1 + label_w + (pad_x * 2), label_y2),
            color,
            -1,
            cv2.LINE_AA,
        )
        cv2.addWeighted(label_overlay, 0.78, image, 0.22, 0, image)
        cv2.putText(
            image,
            label,
            (label_x1 + pad_x, label_y1 + pad_y + label_h),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (20, 24, 31),
            font_thickness,
            cv2.LINE_AA,
        )

    return image


def extract_semantic_classes(result) -> list:
    semantic_mask = getattr(result, 'semantic_mask', None)
    if semantic_mask is None or getattr(semantic_mask, 'data', None) is None:
        return []

    class_map = semantic_mask.data.detach().cpu().numpy()
    ids, counts = np.unique(class_map, return_counts=True)
    total = max(1, class_map.size)
    classes = []
    for cls_id, count in sorted(zip(ids, counts), key=lambda item: item[1], reverse=True):
        cls_id = int(cls_id)
        if cls_id == 255:
            continue
        classes.append({
            "class": result.names.get(cls_id, f"class_{cls_id}"),
            "coverage": round(float(count) / total, 4),
        })
    return classes


def analyze_image_yolo(file_path: str, model_type: str, confidence: float = 0.25) -> dict:
    model = get_model(model_type)

    results = model.predict(file_path, conf=confidence, verbose=False)
    if not results:
        raise ValueError("No results returned from YOLO model")

    result = results[0]

    # Generate annotated image
    annotated = render_clean_annotations(result)
    _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    # Extract detection data
    detections = []
    semantic_classes = extract_semantic_classes(result)
    if semantic_classes:
        detections = semantic_classes
    elif hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].tolist()
            class_name = result.names.get(cls_id, f"class_{cls_id}")
            detections.append({
                "class": class_name,
                "confidence": round(conf, 3),
                "bbox": [round(x, 1) for x in xyxy],
            })
        detections.sort(key=lambda x: x['confidence'], reverse=True)

    suggestions = _generate_suggestions(model_type, detections)

    return {
        "type": "image",
        "content": f"data:image/jpeg;base64,{b64}",
        "detections": detections,
        "suggestions": suggestions,
    }


def _generate_suggestions(model_type: str, detections: list) -> list:
    classes = list(dict.fromkeys(d['class'] for d in detections[:5]))
    count = len(detections)

    if model_type == 'yolo26':
        base = [
            f"Segment {classes[0]} objects" if classes else "Run instance segmentation",
            "Describe with Gemini vision",
            f"Count: {count} objects detected — refine confidence",
        ]
    elif model_type == 'yolo26-seg':
        base = [
            "Run semantic scene analysis",
            "Describe segmentation with Gemini",
            f"Focus on {classes[0]}" if classes else "Adjust detection confidence",
        ]
    else:  # yolo26-sem
        base = [
            "Run instance segmentation",
            "Detect specific objects",
            "Describe the full scene with Gemini",
        ]

    return base[:3]
