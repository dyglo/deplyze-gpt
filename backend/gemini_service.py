import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
import google.auth
from google.api_core import exceptions as google_exceptions
from google.cloud import storage
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel, Image, Part

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
HIGH_DEMAND_MESSAGE = "Our AI model is experiencing high demand. Please try again in a moment."
GENERIC_GEMINI_MESSAGE = "Gemini analysis failed. Please try again."
GOOGLE_CLOUD_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
RETRY_DELAYS_SECONDS = (2, 4, 8)

_CREDENTIALS = None
_STORAGE_CLIENT = None
_VERTEX_INITIALIZED = False


class GeminiServiceError(RuntimeError):
    pass


def _vertex_project() -> str:
    return (
        os.environ.get("VERTEX_AI_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or "vision-sys"
    )


def _vertex_location() -> str:
    return os.environ.get("VERTEX_AI_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"


def _vertex_gcs_bucket() -> str:
    return (
        os.environ.get("VERTEX_GCS_BUCKET")
        or os.environ.get("VERTEX_STAGING_BUCKET")
        or os.environ.get("FIREBASE_STORAGE_BUCKET")
        or "vision-sys.firebasestorage.app"
    )


def _resolve_service_account_path() -> Path | None:
    configured = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        return path

    matches = sorted(PROJECT_ROOT.glob("*firebase-adminsdk*.json"))
    return matches[0] if matches else None


def _service_account_info() -> dict | None:
    encoded = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON_B64")
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if encoded:
        raw = base64.b64decode(encoded).decode("utf-8")
    return json.loads(raw) if raw else None


def _get_google_credentials():
    global _CREDENTIALS

    if _CREDENTIALS is not None:
        return _CREDENTIALS

    service_account_info = _service_account_info()
    if service_account_info:
        _CREDENTIALS = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=GOOGLE_CLOUD_SCOPES,
        )
        return _CREDENTIALS

    service_account_path = _resolve_service_account_path()
    if service_account_path and service_account_path.exists():
        _CREDENTIALS = service_account.Credentials.from_service_account_file(
            str(service_account_path),
            scopes=GOOGLE_CLOUD_SCOPES,
        )
        return _CREDENTIALS

    try:
        _CREDENTIALS, _ = google.auth.default(scopes=GOOGLE_CLOUD_SCOPES)
        return _CREDENTIALS
    except Exception as exc:
        logger.error("Vertex AI credentials could not be resolved: %s", exc, exc_info=True)
        raise GeminiServiceError("Gemini is not configured. Check Vertex AI credentials.") from exc


def _initialize_vertex():
    global _VERTEX_INITIALIZED

    if _VERTEX_INITIALIZED:
        return

    vertexai.init(
        project=_vertex_project(),
        location=_vertex_location(),
        credentials=_get_google_credentials(),
    )
    _VERTEX_INITIALIZED = True


def _get_storage_client() -> storage.Client:
    global _STORAGE_CLIENT

    if _STORAGE_CLIENT is None:
        _STORAGE_CLIENT = storage.Client(project=_vertex_project(), credentials=_get_google_credentials())
    return _STORAGE_CLIENT


def _get_model(system_prompt: str) -> GenerativeModel:
    _initialize_vertex()
    return GenerativeModel(GEMINI_MODEL, system_instruction=[system_prompt])


def _generate_config() -> GenerationConfig:
    return GenerationConfig(max_output_tokens=2048)


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, (google_exceptions.ResourceExhausted, google_exceptions.TooManyRequests)):
        return True

    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    if str(code).lower() in {"429", "statuscode.resource_exhausted", "resource_exhausted"}:
        return True

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "rate-limit",
            "too many requests",
        )
    )


def _exception_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    return str(code) if code is not None else ""


def _exception_error_details(exc: Exception) -> list:
    details = []

    for attr in ("errors", "details"):
        value = getattr(exc, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value:
            details.append(str(value))

    return details


def _log_vertex_error(exc: Exception, *, operation: str, attempt: int | None = None):
    payload = {
        "severity": "ERROR",
        "event": "vertex_gemini_error",
        "operation": operation,
        "attempt": attempt,
        "model": GEMINI_MODEL,
        "vertex_project": _vertex_project(),
        "vertex_location": _vertex_location(),
        "exception_type": type(exc).__name__,
        "exception_code": _exception_code(exc),
        "exception_message": str(exc),
        "error_details": _exception_error_details(exc),
    }
    print(json.dumps(payload, default=str), file=sys.stderr, flush=True)


def clean_gemini_error(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if _is_quota_or_rate_limit_error(exc):
        return HIGH_DEMAND_MESSAGE
    if "503" in lower or "unavailable" in lower or "high demand" in lower:
        return "Gemini is temporarily busy. Please try again in a moment."
    if "permission" in lower or "unauthorized" in lower or "forbidden" in lower:
        return "Gemini is not available right now. Please try again later."
    if "timeout" in lower:
        return "Gemini took too long to respond. Please try again."
    return GENERIC_GEMINI_MESSAGE


def _raise_clean_gemini_error(exc: Exception):
    _log_vertex_error(exc, operation="generate_content")
    logger.warning("Gemini provider error: %s", exc, exc_info=True)
    raise GeminiServiceError(clean_gemini_error(exc)) from exc


def _generate_with_retry(operation):
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            return operation()
        except Exception as exc:
            if not _is_quota_or_rate_limit_error(exc):
                _raise_clean_gemini_error(exc)

            if attempt >= len(RETRY_DELAYS_SECONDS):
                _log_vertex_error(exc, operation="generate_content", attempt=attempt + 1)
                logger.warning("Vertex Gemini quota/rate limit exhausted after retries: %s", exc, exc_info=True)
                raise GeminiServiceError(HIGH_DEMAND_MESSAGE) from exc

            delay = RETRY_DELAYS_SECONDS[attempt]
            _log_vertex_error(exc, operation="generate_content_retryable", attempt=attempt + 1)
            logger.info("Vertex Gemini quota/rate limit encountered. Retrying in %s seconds.", delay)
            time.sleep(delay)

DOMAIN_PROMPTS = {
    "medical": (
        "You are a medical imaging AI assistant. Analyze images with clinical precision, "
        "using proper anatomical and medical terminology. Focus on clinically relevant observations."
    ),
    "construction": (
        "You are a construction site AI assistant. Analyze images for safety compliance, "
        "structural elements, and site conditions. Use construction industry terminology."
    ),
    "agriculture": (
        "You are an agricultural AI assistant. Analyze images for plant health, crop conditions, "
        "soil quality, and farming best practices."
    ),
    "retail": (
        "You are a retail analytics AI assistant. Analyze images for product placement, "
        "inventory visibility, and retail optimization opportunities."
    ),
    "research": (
        "You are a research imaging AI assistant. Analyze images with scientific rigor and precision, "
        "noting observations relevant to research methodology."
    ),
}

DEFAULT_SYSTEM = """You are DeplyzeGPT, an advanced computer vision AI assistant.
Analyze images and videos with precision and provide detailed, structured insights.
Include: key visual elements, spatial relationships, notable patterns, and actionable insights.
Always end your response with exactly 3 follow-up action suggestions in this format:

Suggestions:
1. [actionable suggestion]
2. [actionable suggestion]
3. [actionable suggestion]"""

DOMAIN_KEYWORDS = {
    "medical": ["medical", "xray", "x-ray", "mri", "scan", "patient", "clinical", "anatomy", "diagnosis", "hospital", "ct"],
    "construction": ["construction", "building", "scaffold", "safety", "worker", "site", "crane"],
    "agriculture": ["agriculture", "crop", "farm", "plant", "field", "harvest", "soil", "irrigation"],
    "retail": ["retail", "store", "product", "shelf", "inventory", "customer", "shopping", "supermarket"],
    "research": ["research", "lab", "experiment", "specimen", "microscope", "scientific"],
}

MIME_IMAGE = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
MIME_VIDEO = {"mp4": "video/mp4", "mov": "video/quicktime", "avi": "video/x-msvideo"}
FALLBACK_SUGGESTIONS = [
    "Run object detection with YOLO26",
    "Analyze with instance segmentation",
    "Export analysis results",
]


def _get_system_prompt(prompt: str) -> str:
    lower = prompt.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            suffix = "\n\nAlways end with:\nSuggestions:\n1. ...\n2. ...\n3. ..."
            return DOMAIN_PROMPTS[domain] + suffix
    return DEFAULT_SYSTEM


def _extract_suggestions(text: str) -> list:
    match = re.search(r"Suggestions?:?\s*\n((?:\s*\d+[.)]\s*.+\n?){1,5})", text, re.IGNORECASE)
    if match:
        block = match.group(1)
        items = re.findall(r"\d+[.)]\s*(.+)", block)
        return [s.strip() for s in items[:3]]

    all_numbered = re.findall(r"(?:^|\n)\d+[.)]\s*(.+)", text)
    if len(all_numbered) >= 2:
        return [s.strip() for s in all_numbered[-3:]]
    return []


def _response_text(response) -> str:
    if getattr(response, "text", None):
        return response.text.strip()

    parts = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _build_result(text: str, fallback_suggestions: list = None) -> dict:
    suggestions = _extract_suggestions(text)
    return {
        "type": "text",
        "content": text,
        "detections": [],
        "suggestions": suggestions if suggestions else (fallback_suggestions or FALLBACK_SUGGESTIONS),
    }


def _upload_video_to_gcs(path: Path, mime_type: str):
    bucket_name = _vertex_gcs_bucket()
    if not bucket_name:
        raise GeminiServiceError("Gemini video analysis is not configured. Add VERTEX_GCS_BUCKET.")

    blob_name = f"gemini-inputs/{uuid.uuid4().hex}/{path.name}"
    try:
        bucket = _get_storage_client().bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(path), content_type=mime_type)
        return f"gs://{bucket_name}/{blob_name}", blob
    except Exception as exc:
        logger.error("Gemini video staging upload failed: %s", exc, exc_info=True)
        raise GeminiServiceError(GENERIC_GEMINI_MESSAGE) from exc


def _analyze_image_sync(file_path: str, prompt: str, system_prompt: str) -> dict:
    path = Path(file_path)

    model = _get_model(system_prompt)
    image_part = Part.from_image(Image.load_from_file(str(path)))
    response = _generate_with_retry(
        lambda: model.generate_content(
            contents=[
                Part.from_text(prompt),
                image_part,
            ],
            generation_config=_generate_config(),
        )
    )
    return _build_result(_response_text(response))


def _analyze_video_sync(file_path: str, prompt: str, system_prompt: str) -> dict:
    path = Path(file_path)
    ext = path.suffix.lower().lstrip(".")
    mime_type = MIME_VIDEO.get(ext, "video/mp4")

    gcs_uri = None
    staged_blob = None
    try:
        gcs_uri, staged_blob = _upload_video_to_gcs(path, mime_type)
        model = _get_model(system_prompt)
        video_part = Part.from_uri(uri=gcs_uri, mime_type=mime_type)
        response = _generate_with_retry(
            lambda: model.generate_content(
                contents=[
                    Part.from_text(prompt),
                    video_part,
                ],
                generation_config=_generate_config(),
            )
        )
        return _build_result(
            _response_text(response),
            [
                "Run YOLO detection on video frames",
                "Analyze specific time segments",
                "Export frame-by-frame analysis",
            ],
        )
    finally:
        if staged_blob is not None:
            try:
                staged_blob.delete()
            except Exception as exc:
                logger.warning("Gemini staged video cleanup failed for %s: %s", gcs_uri, exc)


async def analyze_image_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)
    return await asyncio.to_thread(_analyze_image_sync, file_path, prompt, system_prompt)


async def analyze_video_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)
    return await asyncio.to_thread(_analyze_video_sync, file_path, prompt, system_prompt)
