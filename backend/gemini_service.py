import asyncio
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


class GeminiServiceError(RuntimeError):
    pass


def clean_gemini_error(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if "503" in lower or "unavailable" in lower or "high demand" in lower:
        return "Gemini is temporarily busy. Please try again in a moment."
    if "429" in lower or "quota" in lower or "rate limit" in lower:
        return "Gemini usage limit was reached. Please wait a bit and try again."
    if "api key" in lower or "permission" in lower or "unauthorized" in lower:
        return "Gemini is not available right now. Check the API key configuration."
    if "timeout" in lower:
        return "Gemini took too long to respond. Please try again."
    return "Gemini analysis failed. Please try again."


def _raise_clean_gemini_error(exc: Exception):
    logger.warning("Gemini provider error: %s", exc)
    raise GeminiServiceError(clean_gemini_error(exc)) from exc

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


def _get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise GeminiServiceError("Gemini is not configured. Add GEMINI_API_KEY to backend/.env.")
    return genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1beta"})


def _generate_config(system_prompt: str) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        systemInstruction=system_prompt,
        maxOutputTokens=2048,
        thinkingConfig=types.ThinkingConfig(thinkingBudget=0),
    )


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


def _state_name(file_obj) -> str:
    state = getattr(file_obj, "state", None)
    return getattr(state, "name", str(state)).upper()


def _wait_for_uploaded_file(client: genai.Client, uploaded_file, timeout_seconds: int = 300):
    deadline = time.monotonic() + timeout_seconds
    current = uploaded_file

    while _state_name(current).endswith("PROCESSING"):
        if time.monotonic() >= deadline:
            raise TimeoutError("Gemini video upload processing timed out")
        time.sleep(2)
        current = client.files.get(name=current.name)

    state = _state_name(current)
    if not state.endswith("ACTIVE"):
        raise RuntimeError(f"Gemini video upload failed with state: {state}")
    return current


def _build_result(text: str, fallback_suggestions: list = None) -> dict:
    suggestions = _extract_suggestions(text)
    return {
        "type": "text",
        "content": text,
        "detections": [],
        "suggestions": suggestions if suggestions else (fallback_suggestions or FALLBACK_SUGGESTIONS),
    }


def _analyze_image_sync(file_path: str, prompt: str, system_prompt: str) -> dict:
    path = Path(file_path)
    ext = path.suffix.lower().lstrip(".")
    mime_type = MIME_IMAGE.get(ext, "image/jpeg")

    client = _get_client()
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type),
            ],
            config=_generate_config(system_prompt),
        )
    except Exception as exc:
        _raise_clean_gemini_error(exc)
    return _build_result(_response_text(response))


def _analyze_video_sync(file_path: str, prompt: str, system_prompt: str) -> dict:
    path = Path(file_path)
    ext = path.suffix.lower().lstrip(".")
    mime_type = MIME_VIDEO.get(ext, "video/mp4")

    client = _get_client()
    try:
        uploaded_file = client.files.upload(
            file=str(path),
            config=types.UploadFileConfig(mimeType=mime_type, displayName=path.name),
        )
    except Exception as exc:
        _raise_clean_gemini_error(exc)

    try:
        try:
            active_file = _wait_for_uploaded_file(client, uploaded_file)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_text(text=prompt),
                    active_file,
                ],
                config=_generate_config(system_prompt),
            )
        except Exception as exc:
            _raise_clean_gemini_error(exc)
        return _build_result(
            _response_text(response),
            [
                "Run YOLO detection on video frames",
                "Analyze specific time segments",
                "Export frame-by-frame analysis",
            ],
        )
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception as exc:
            logger.warning("Gemini uploaded-file cleanup failed: %s", exc)


async def analyze_image_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)
    return await asyncio.to_thread(_analyze_image_sync, file_path, prompt, system_prompt)


async def analyze_video_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)
    return await asyncio.to_thread(_analyze_video_sync, file_path, prompt, system_prompt)
