import cv2
import base64
import logging
from pathlib import Path
from ultralytics import YOLO

logger = logging.getLogger(__name__)

_models: dict = {}

MODEL_MAP = {
    'yolo26': 'yolo26n.pt',
    'yolo26-seg': 'yolo26n-seg.pt',
    'yolo26-sem': 'yolo26n-sem.pt',
}


def get_model(model_type: str) -> YOLO:
    if model_type not in _models:
        model_name = MODEL_MAP.get(model_type, 'yolo26n.pt')
        model_path = Path(__file__).parent / model_name
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file '{model_name}' not found. "
                f"Available models: {list(MODEL_MAP.keys())[:2]}"
            )
        logger.info(f"Loading YOLO model: {model_name}")
        _models[model_type] = YOLO(str(model_path))
        logger.info(f"YOLO model {model_name} ready")
    return _models[model_type]


def analyze_image_yolo(file_path: str, model_type: str, confidence: float = 0.25) -> dict:
    model = get_model(model_type)

    results = model.predict(file_path, conf=confidence, verbose=False)
    if not results:
        raise ValueError("No results returned from YOLO model")

    result = results[0]

    # Generate annotated image
    annotated = result.plot()
    _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    # Extract detection data
    detections = []
    if hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
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
