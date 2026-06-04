import cv2
import base64
import logging
import numpy as np
import os
import re
import shutil
from dataclasses import dataclass
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

CLASS_FILTER_INTENTS = {
    "detect",
    "find",
    "segment",
    "count",
    "show",
    "filter",
    "focus",
}

CLASS_FILTER_IGNORE_WORDS = {
    "a",
    "all",
    "an",
    "analyze",
    "and",
    "around",
    "are",
    "at",
    "back",
    "background",
    "black",
    "blue",
    "brown",
    "can",
    "center",
    "class",
    "classes",
    "could",
    "day",
    "daytime",
    "describe",
    "detail",
    "detailed",
    "details",
    "detection",
    "everything",
    "far",
    "for",
    "foreground",
    "frame",
    "frames",
    "front",
    "from",
    "full",
    "green",
    "grey",
    "gray",
    "high",
    "image",
    "in",
    "inside",
    "indoors",
    "item",
    "items",
    "just",
    "large",
    "left",
    "low",
    "matching",
    "me",
    "moving",
    "near",
    "night",
    "nighttime",
    "object",
    "objects",
    "of",
    "on",
    "only",
    "orange",
    "or",
    "outdoors",
    "outside",
    "parked",
    "parking",
    "photo",
    "picture",
    "pink",
    "please",
    "perform",
    "purple",
    "red",
    "right",
    "scene",
    "selected",
    "semantic",
    "should",
    "sitting",
    "small",
    "specific",
    "standing",
    "segmentation",
    "segmenting",
    "the",
    "thing",
    "things",
    "this",
    "to",
    "video",
    "visible",
    "what",
    "white",
    "with",
    "yellow",
    "you",
    "lot",
}

ALL_CLASS_PHRASES = {
    "all",
    "all classes",
    "all objects",
    "all items",
    "all things",
    "everything",
    "full scene",
    "the full scene",
}

MODEL_LABELS = {
    "yolo26": "YOLO26 Detection",
    "yolo26-seg": "YOLO26 Segmentation",
    "yolo26-sem": "YOLO26 Semantic",
}


@dataclass(frozen=True)
class ClassFilter:
    ids: list
    names: list


class ClassFilterError(ValueError):
    pass


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


def _normalize_text(value: str) -> str:
    text = (value or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pluralize_word(word: str) -> str:
    if not word:
        return word
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return f"{word[:-1]}ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return f"{word}es"
    return f"{word}s"


def _class_variants(name: str) -> set:
    normalized = _normalize_text(name)
    variants = {normalized}
    parts = normalized.split()
    if parts:
        variants.add(" ".join([*parts[:-1], _pluralize_word(parts[-1])]))
    return {variant for variant in variants if variant}


COMMON_CLASS_ALIASES = {
    "airplane": ["aeroplane", "aeroplanes", "aircraft", "plane", "planes"],
    "bicycle": ["bike", "bikes", "cycle", "cycles"],
    "car": ["automobile", "automobiles", "auto", "autos", "cars"],
    "cell phone": ["mobile phone", "mobile phones", "phone", "phones"],
    "couch": ["sofa", "sofas"],
    "dining table": ["table", "tables"],
    "hair drier": ["hair dryer", "hair dryers"],
    "motorcycle": ["motorbike", "motorbikes"],
    "person": ["human", "humans", "people", "persons"],
    "potted plant": ["plant", "plants"],
    "road": ["roads", "street", "streets"],
    "sidewalk": ["pavement", "pavements", "walkway", "walkways"],
    "sports ball": ["ball", "balls"],
    "traffic sign": ["sign", "signs", "traffic signs"],
    "truck": ["lorry", "lorries", "van", "vans", "delivery van", "delivery vans"],
    "tv": ["television", "televisions", "tvs"],
    "vegetation": ["plant", "plants", "trees"],
}


def _class_name_pairs(names: dict) -> list:
    return [(int(cls_id), str(name)) for cls_id, name in sorted(names.items(), key=lambda item: int(item[0]))]


def _class_alias_map(names: dict) -> dict:
    pairs = _class_name_pairs(names)
    by_name = {_normalize_text(name): (cls_id, name) for cls_id, name in pairs}
    aliases = {}

    for cls_id, name in pairs:
        for variant in _class_variants(name):
            aliases[variant] = (cls_id, name)

    for target_name, target_aliases in COMMON_CLASS_ALIASES.items():
        target = by_name.get(target_name)
        if not target:
            continue
        for alias in target_aliases:
            normalized = _normalize_text(alias)
            if normalized:
                aliases[normalized] = target

    return aliases


def _is_all_classes_request(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return True
    if normalized in ALL_CLASS_PHRASES:
        return True
    if "full scene" in normalized:
        return True
    return bool(
        re.search(r"\b(?:all|every|everything)\b.*\b(?:classes|items|objects|things)\b", normalized)
    )


def _extract_filter_region(prompt: str) -> str:
    text = _normalize_text(prompt)
    if not text or _is_all_classes_request(text):
        return ""

    patterns = [
        r"\b(?:only|just)\b\s+(.+)",
        r"\bperform\s+(?:semantic\s+|instance\s+)?segmentation\s+(?:on|of|for)?\s*(.+)",
        r"\bsemantic\s+segmentation\s+(?:on|of|for)?\s*(.+)",
        r"\binstance\s+segmentation\s+(?:on|of|for)?\s*(.+)",
        r"\b(?:focus|filter)\s+(?:on|to|for)?\s*(.+)",
        r"\blook\s+for\s+(.+)",
        r"\b(?:detect|find|segment|count|show)\b\s+(?:only\s+|just\s+)?(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        region = match.group(1).strip()
        return "" if _is_all_classes_request(region) else region

    tokens = text.split()
    if len(tokens) <= 8:
        return text
    return ""


def _has_explicit_filter_intent(prompt: str) -> bool:
    text = _normalize_text(prompt)
    return bool(
        re.search(r"\b(?:only|just|filter|focus|detect|find|segment|count|show)\b", text)
        or re.search(r"\blook\s+for\b", text)
    )


def _find_class_matches(text: str, aliases: dict) -> list:
    matches = []
    occupied = [False] * len(text)

    for alias, (cls_id, class_name) in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
        for match in re.finditer(pattern, text):
            start, end = match.span()
            if any(occupied[start:end]):
                continue
            for index in range(start, end):
                occupied[index] = True
            matches.append({
                "start": start,
                "end": end,
                "id": cls_id,
                "name": class_name,
            })

    return sorted(matches, key=lambda item: item["start"])


def _unknown_filter_terms(text: str, matches: list) -> list:
    chars = list(text)
    for match in matches:
        for index in range(match["start"], match["end"]):
            chars[index] = " "

    residual = re.sub(r"\s+", " ", "".join(chars)).strip()
    if not residual:
        return []

    unknowns = []
    for chunk in re.split(r"\b(?:and|or)\b", residual):
        tokens = [
            token
            for token in chunk.split()
            if token not in CLASS_FILTER_IGNORE_WORDS and token not in CLASS_FILTER_INTENTS
        ]
        if tokens:
            unknowns.append(" ".join(tokens))

    return list(dict.fromkeys(unknowns))


def _available_class_names(names: dict) -> list:
    return [name for _, name in _class_name_pairs(names)]


def _class_filter_error_message(model_type: str, unknowns: list, names: dict) -> str:
    model_label = MODEL_LABELS.get(model_type, model_type)
    unknown_text = ", ".join(unknowns)
    available_names = _available_class_names(names)
    examples = ", ".join(available_names[:12])
    remaining = len(available_names) - 12
    suffix = f", and {remaining} more" if remaining > 0 else ""
    return (
        f"{model_label} does not have a class for: {unknown_text}. "
        f"Try one of the supported classes, for example: {examples}{suffix}."
    )


def resolve_class_filter(prompt: str, model_type: str):
    region = _extract_filter_region(prompt)
    if not region:
        return None

    model = get_model(model_type)
    names = model.names
    matches = _find_class_matches(region, _class_alias_map(names))
    unknowns = _unknown_filter_terms(region, matches)
    if unknowns and (matches or _has_explicit_filter_intent(prompt)):
        raise ClassFilterError(_class_filter_error_message(model_type, unknowns, names))

    if not matches:
        return None

    ids = []
    selected_names = []
    for match in matches:
        if match["id"] in ids:
            continue
        ids.append(match["id"])
        selected_names.append(match["name"])

    return ClassFilter(ids=ids, names=selected_names)


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


def _render_semantic_annotations(result, base_image=None, class_filter_ids=None):
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
    filter_set = set(class_filter_ids) if class_filter_ids is not None else None
    valid = [
        (int(cls_id), int(count))
        for cls_id, count in zip(ids, counts)
        if int(cls_id) != 255 and (filter_set is None or int(cls_id) in filter_set)
    ]

    for cls_id, _ in valid:
        color = np.array(_annotation_color(cls_id), dtype=np.float32)
        mask = class_map == cls_id
        overlay[mask] = (
            (1.0 - SEMANTIC_FILL_ALPHA) * image[mask] + SEMANTIC_FILL_ALPHA * color
        ).astype(np.uint8)

    image = overlay
    _draw_semantic_boundaries(image, class_map, filter_set)
    _draw_semantic_legend(image, result.names, valid, width, height)
    return image


def _draw_semantic_boundaries(image, class_map, class_filter_ids=None):
    horizontal = np.zeros(class_map.shape, dtype=np.uint8)
    vertical = np.zeros(class_map.shape, dtype=np.uint8)
    horizontal[1:, :] = class_map[1:, :] != class_map[:-1, :]
    vertical[:, 1:] = class_map[:, 1:] != class_map[:, :-1]
    edges = cv2.dilate(
        ((horizontal | vertical) * 255).astype(np.uint8),
        np.ones((2, 2), dtype=np.uint8),
        iterations=1,
    )
    if class_filter_ids is not None:
        selected = np.isin(class_map, list(class_filter_ids))
        edges = np.where(selected, edges, 0).astype(np.uint8)
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


def render_clean_annotations(result, base_image=None, class_filter_ids=None):
    if getattr(result, 'semantic_mask', None) is not None:
        return _render_semantic_annotations(result, base_image, class_filter_ids)

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


def extract_semantic_classes(result, class_filter_ids=None) -> list:
    semantic_mask = getattr(result, 'semantic_mask', None)
    if semantic_mask is None or getattr(semantic_mask, 'data', None) is None:
        return []

    class_map = semantic_mask.data.detach().cpu().numpy()
    ids, counts = np.unique(class_map, return_counts=True)
    total = max(1, class_map.size)
    filter_set = set(class_filter_ids) if class_filter_ids is not None else None
    classes = []
    for cls_id, count in sorted(zip(ids, counts), key=lambda item: item[1], reverse=True):
        cls_id = int(cls_id)
        if cls_id == 255 or (filter_set is not None and cls_id not in filter_set):
            continue
        classes.append({
            "class": result.names.get(cls_id, f"class_{cls_id}"),
            "coverage": round(float(count) / total, 4),
        })
    return classes


def analyze_image_yolo(file_path: str, model_type: str, confidence: float = 0.25, class_filter_ids=None) -> dict:
    model = get_model(model_type)

    predict_kwargs = {"conf": confidence, "verbose": False}
    if class_filter_ids is not None:
        predict_kwargs["classes"] = class_filter_ids
    results = model.predict(file_path, **predict_kwargs)
    if not results:
        raise ValueError("No results returned from YOLO model")

    result = results[0]

    # Generate annotated image
    annotated = render_clean_annotations(result, class_filter_ids=class_filter_ids)
    _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    # Extract detection data
    detections = []
    semantic_classes = extract_semantic_classes(result, class_filter_ids=class_filter_ids)
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
