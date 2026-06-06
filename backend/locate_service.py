import base64
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

MODEL_TYPE = "locate-anything"
MODEL_LABEL = "LocateAnything-3B"
DEFAULT_MODEL_ID = "nvidia/LocateAnything-3B"
DEFAULT_GENERATION_MODE = "hybrid"
DEFAULT_MAX_NEW_TOKENS = 8192
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_MAX_REQUEST_SIDE = 1024
DEFAULT_RETRY_DELAY_SECONDS = 5
SUPPORTED_GENERATION_MODES = {"fast", "slow", "hybrid"}
RETRIABLE_STATUS_CODES = {429, 502, 503, 504}

ANNOTATION_PALETTE = [
    (50, 170, 255),
    (74, 222, 128),
    (255, 205, 86),
    (244, 114, 182),
    (45, 212, 191),
    (168, 139, 250),
]

BOX_TOKEN_RE = re.compile(
    r"<box>\s*<\s*(-?\d+(?:\.\d+)?)\s*>\s*<\s*(-?\d+(?:\.\d+)?)\s*>"
    r"\s*<\s*(-?\d+(?:\.\d+)?)\s*>\s*<\s*(-?\d+(?:\.\d+)?)\s*>\s*</box>",
    re.IGNORECASE,
)
POINT_TOKEN_RE = re.compile(
    r"<box>\s*<\s*(-?\d+(?:\.\d+)?)\s*>\s*<\s*(-?\d+(?:\.\d+)?)\s*>\s*</box>",
    re.IGNORECASE,
)
BOX_COMMA_RE = re.compile(
    r"<box>\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,"
    r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*</box>",
    re.IGNORECASE,
)
POINT_COMMA_RE = re.compile(
    r"<box>\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*</box>",
    re.IGNORECASE,
)


class LocateServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class LocateConfigurationError(LocateServiceError):
    pass


class LocateProviderError(LocateServiceError):
    pass


@dataclass(frozen=True)
class LocateDetection:
    kind: str
    label: str
    coordinates: list[float]

    def as_message_detection(self) -> dict:
        if self.kind == "point":
            return {"kind": "point", "class": self.label, "point": self.coordinates}
        return {"kind": "box", "class": self.label, "bbox": self.coordinates}


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def is_locate_enabled() -> bool:
    return _truthy_env("ENABLE_LOCATE_ANYTHING")


def _endpoint_url() -> str:
    return os.environ.get("LOCATE_ENDPOINT_URL", "").strip().rstrip("/")


def _endpoint_audience() -> str:
    return os.environ.get("LOCATE_ENDPOINT_AUDIENCE", "").strip()


def _generation_mode(configured: Optional[str] = None) -> str:
    mode = (configured or os.environ.get("LOCATE_GENERATION_MODE") or DEFAULT_GENERATION_MODE).strip().lower()
    return mode if mode in SUPPORTED_GENERATION_MODES else DEFAULT_GENERATION_MODE


def _timeout_seconds() -> int:
    try:
        value = int(os.environ.get("LOCATE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        value = DEFAULT_TIMEOUT_SECONDS
    return max(30, value)


def _retry_delay_seconds() -> int:
    try:
        value = int(os.environ.get("LOCATE_RETRY_DELAY_SECONDS", str(DEFAULT_RETRY_DELAY_SECONDS)))
    except ValueError:
        value = DEFAULT_RETRY_DELAY_SECONDS
    return min(30, max(1, value))


def _max_new_tokens(configured: Optional[int] = None) -> int:
    if configured is not None:
        return max(1, int(configured))
    try:
        value = int(os.environ.get("LOCATE_MAX_NEW_TOKENS", str(DEFAULT_MAX_NEW_TOKENS)))
    except ValueError:
        value = DEFAULT_MAX_NEW_TOKENS
    return max(1, value)


def _max_request_side() -> int:
    try:
        value = int(os.environ.get("LOCATE_MAX_REQUEST_SIDE", str(DEFAULT_MAX_REQUEST_SIDE)))
    except ValueError:
        value = DEFAULT_MAX_REQUEST_SIDE
    return max(256, value)


def _prediction_url(endpoint: str) -> str:
    return endpoint if endpoint.endswith("/predict") else f"{endpoint}/predict"


def _auth_headers(endpoint: str) -> dict:
    headers = {"Content-Type": "application/json"}
    audience = _endpoint_audience()
    if audience:
        token = id_token.fetch_id_token(GoogleAuthRequest(), audience)
        headers["Authorization"] = f"Bearer {token}"
    elif os.environ.get("LOCATE_BEARER_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['LOCATE_BEARER_TOKEN']}"
    return headers


def _encode_image_jpeg(file_path: str) -> tuple[str, np.ndarray]:
    image = cv2.imread(str(file_path))
    if image is None:
        raise LocateServiceError("Could not read image for LocateAnything analysis.", status_code=422)

    request_image = _resize_for_request(image)
    ok, buf = cv2.imencode(".jpg", request_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise LocateServiceError("Could not encode image for LocateAnything analysis.", status_code=500)

    return base64.b64encode(buf.tobytes()).decode("utf-8"), image


def _resize_for_request(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    max_side = _max_request_side()
    longest = max(width, height)
    if longest <= max_side:
        return image

    scale = max_side / longest
    out_width = max(1, int(round(width * scale)))
    out_height = max(1, int(round(height * scale)))
    return cv2.resize(image, (out_width, out_height), interpolation=cv2.INTER_AREA)


def _call_locate_endpoint(
    image_b64: str,
    prompt: str,
    generation_mode: str,
    max_new_tokens: int,
) -> dict[str, Any]:
    if not is_locate_enabled():
        raise LocateConfigurationError(
            "LocateAnything is disabled. Set ENABLE_LOCATE_ANYTHING=true to enable the research preview."
        )

    endpoint = _endpoint_url()
    if not endpoint:
        raise LocateConfigurationError("LocateAnything is not configured. Add LOCATE_ENDPOINT_URL.")

    payload = {
        "image_b64": image_b64,
        "prompt": prompt,
        "generation_mode": generation_mode,
        "max_new_tokens": max_new_tokens,
    }

    timeout_seconds = _timeout_seconds()
    retry_delay = _retry_delay_seconds()
    deadline = time.monotonic() + timeout_seconds

    try:
        headers = _auth_headers(endpoint)
    except Exception as exc:
        logger.error("LocateAnything authentication/setup failed: %s", exc, exc_info=True)
        raise LocateProviderError("LocateAnything is not available right now. Please try again later.") from exc

    attempt = 0
    while True:
        attempt += 1
        remaining_timeout = max(1, deadline - time.monotonic())
        try:
            response = requests.post(
                _prediction_url(endpoint),
                json=payload,
                headers=headers,
                timeout=remaining_timeout,
            )
        except requests.Timeout as exc:
            raise LocateProviderError("LocateAnything took too long to respond. Please try again.") from exc
        except requests.RequestException as exc:
            logger.error("LocateAnything request failed: %s", exc, exc_info=True)
            raise LocateProviderError("LocateAnything is not available right now. Please try again later.") from exc

        if response.status_code not in RETRIABLE_STATUS_CODES:
            break

        detail = response.text[:300]
        if time.monotonic() + retry_delay >= deadline:
            logger.warning(
                "LocateAnything endpoint stayed unavailable after %s attempts; last response %s: %s",
                attempt,
                response.status_code,
                detail,
            )
            raise LocateProviderError(
                "LocateAnything is starting or temporarily busy. Please try again in a moment.",
                status_code=503,
            )

        logger.info(
            "LocateAnything endpoint returned %s on attempt %s; retrying in %ss.",
            response.status_code,
            attempt,
            retry_delay,
        )
        time.sleep(retry_delay)

    if response.status_code >= 400:
        detail = response.text[:300]
        logger.warning("LocateAnything endpoint returned %s: %s", response.status_code, detail)
        raise LocateProviderError("LocateAnything analysis failed. Please try again later.", status_code=502)

    try:
        data = response.json()
    except ValueError as exc:
        raise LocateProviderError("LocateAnything returned an invalid response.", status_code=502) from exc

    if not isinstance(data, dict) or not data.get("answer"):
        raise LocateProviderError("LocateAnything returned no answer.", status_code=502)

    return data


def _clean_label(prompt: str, max_len: int = 72) -> str:
    label = re.sub(r"\s+", " ", (prompt or "").strip())
    label = re.sub(r"^(locate|find|detect|show|point to|ground)\s+", "", label, flags=re.IGNORECASE)
    label = label.strip(" .:")
    if not label:
        return "target"
    return label[:max_len].rstrip()


def _clamp_norm(value: float) -> float:
    return min(1000.0, max(0.0, float(value)))


def _scale_x(value: float, width: int) -> float:
    return round((_clamp_norm(value) / 1000.0) * width, 1)


def _scale_y(value: float, height: int) -> float:
    return round((_clamp_norm(value) / 1000.0) * height, 1)


def _iter_box_matches(answer: str):
    yield from BOX_TOKEN_RE.finditer(answer or "")
    yield from BOX_COMMA_RE.finditer(answer or "")


def _iter_point_matches(answer: str):
    yield from POINT_TOKEN_RE.finditer(answer or "")
    yield from POINT_COMMA_RE.finditer(answer or "")


def parse_locate_output(answer: str, image_width: int, image_height: int, label: str = "target") -> list[dict]:
    detections: list[LocateDetection] = []

    for match in _iter_box_matches(answer):
        x1_raw, y1_raw, x2_raw, y2_raw = [float(value) for value in match.groups()]
        x1, x2 = sorted([_scale_x(x1_raw, image_width), _scale_x(x2_raw, image_width)])
        y1, y2 = sorted([_scale_y(y1_raw, image_height), _scale_y(y2_raw, image_height)])
        if x2 <= x1 or y2 <= y1:
            continue
        detections.append(LocateDetection("box", label, [x1, y1, x2, y2]))

    for match in _iter_point_matches(answer):
        x_raw, y_raw = [float(value) for value in match.groups()]
        detections.append(LocateDetection("point", label, [_scale_x(x_raw, image_width), _scale_y(y_raw, image_height)]))

    return [detection.as_message_detection() for detection in detections]


def _annotation_color(index: int) -> tuple[int, int, int]:
    color = ANNOTATION_PALETTE[index % len(ANNOTATION_PALETTE)]
    return int(color[0]), int(color[1]), int(color[2])


def _annotation_box_thickness(width: int, height: int) -> int:
    return max(3, min(7, round(min(width, height) / 220)))


def _draw_label(image: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    height, width = image.shape[:2]
    font_scale = max(0.42, min(0.68, width / 1800))
    font_thickness = max(1, min(2, round(min(width, height) / 480)))
    pad_x, pad_y = 6, 4
    label = text[:72]
    (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
    label_total_h = label_h + (pad_y * 2) + baseline
    label_x1 = max(0, min(x, width - label_w - (pad_x * 2)))
    label_y1 = max(0, y - label_total_h)
    label_y2 = min(height, label_y1 + label_total_h)

    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (label_x1, label_y1),
        (label_x1 + label_w + (pad_x * 2), label_y2),
        color,
        -1,
        cv2.LINE_AA,
    )
    cv2.addWeighted(overlay, 0.78, image, 0.22, 0, image)
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


def render_locate_annotations(image: np.ndarray, detections: list[dict]) -> np.ndarray:
    annotated = image.copy()
    height, width = annotated.shape[:2]
    thickness = _annotation_box_thickness(width, height)

    for index, detection in enumerate(detections):
        color = _annotation_color(index)
        label = detection.get("class") or "target"
        if detection.get("kind") == "point" and detection.get("point"):
            x, y = [int(round(value)) for value in detection["point"]]
            radius = max(8, thickness * 3)
            cv2.circle(annotated, (x, y), radius, color, thickness, cv2.LINE_AA)
            cv2.line(annotated, (x - radius - 6, y), (x + radius + 6, y), color, thickness, cv2.LINE_AA)
            cv2.line(annotated, (x, y - radius - 6), (x, y + radius + 6), color, thickness, cv2.LINE_AA)
            _draw_label(annotated, label, min(width - 1, x + radius + 8), max(0, y - radius), color)
            continue

        bbox = detection.get("bbox")
        if not bbox:
            continue
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        _draw_label(annotated, label, x1, y1, color)

    return annotated


def _generate_suggestions(prompt: str, detections: list[dict]) -> list[str]:
    label = _clean_label(prompt, max_len=36)
    if detections:
        return [
            f"Point to {label}",
            f"Locate all instances of {label}",
            "Describe this image with Gemini",
        ]
    return [
        "Try a more specific visual description",
        "Point to the target instead",
        "Describe this image with Gemini",
    ]


def analyze_image_locate(
    file_path: str,
    prompt: str,
    generation_mode: Optional[str] = None,
    max_new_tokens: Optional[int] = None,
) -> dict:
    image_b64, image = _encode_image_jpeg(file_path)
    height, width = image.shape[:2]
    label = _clean_label(prompt)
    mode = _generation_mode(generation_mode)

    result = _call_locate_endpoint(
        image_b64=image_b64,
        prompt=prompt or "Locate the most relevant object in this image.",
        generation_mode=mode,
        max_new_tokens=_max_new_tokens(max_new_tokens),
    )
    answer = str(result.get("answer", ""))
    detections = parse_locate_output(answer, width, height, label=label)
    annotated = render_locate_annotations(image, detections)

    ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise LocateServiceError("Could not encode LocateAnything output.", status_code=500)

    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    return {
        "type": "image",
        "content": f"data:image/jpeg;base64,{b64}",
        "detections": detections,
        "suggestions": _generate_suggestions(prompt, detections),
        "raw_answer": answer,
        "generation_mode": mode,
        "model": DEFAULT_MODEL_ID,
        "source_filename": Path(file_path).name,
    }
