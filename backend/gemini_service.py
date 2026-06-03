import os
import uuid
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, TextDelta, StreamDone

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

DOMAIN_PROMPTS = {
    'medical': (
        "You are a medical imaging AI assistant. Analyze images with clinical precision, "
        "using proper anatomical and medical terminology. Focus on clinically relevant observations."
    ),
    'construction': (
        "You are a construction site AI assistant. Analyze images for safety compliance, "
        "structural elements, and site conditions. Use construction industry terminology."
    ),
    'agriculture': (
        "You are an agricultural AI assistant. Analyze images for plant health, crop conditions, "
        "soil quality, and farming best practices."
    ),
    'retail': (
        "You are a retail analytics AI assistant. Analyze images for product placement, "
        "inventory visibility, and retail optimization opportunities."
    ),
    'research': (
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
    'medical': ['medical', 'xray', 'x-ray', 'mri', 'scan', 'patient', 'clinical', 'anatomy', 'diagnosis', 'hospital', 'ct'],
    'construction': ['construction', 'building', 'scaffold', 'safety', 'worker', 'site', 'crane'],
    'agriculture': ['agriculture', 'crop', 'farm', 'plant', 'field', 'harvest', 'soil', 'irrigation'],
    'retail': ['retail', 'store', 'product', 'shelf', 'inventory', 'customer', 'shopping', 'supermarket'],
    'research': ['research', 'lab', 'experiment', 'specimen', 'microscope', 'scientific'],
}

MIME_IMAGE = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
MIME_VIDEO = {'mp4': 'video/mp4', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo'}


def _get_system_prompt(prompt: str) -> str:
    lower = prompt.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            suffix = "\n\nAlways end with:\nSuggestions:\n1. ...\n2. ...\n3. ..."
            return DOMAIN_PROMPTS[domain] + suffix
    return DEFAULT_SYSTEM


def _extract_suggestions(text: str) -> list:
    match = re.search(r'Suggestions?:?\s*\n((?:\s*\d+[.)]\s*.+\n?){1,5})', text, re.IGNORECASE)
    if match:
        block = match.group(1)
        items = re.findall(r'\d+[.)]\s*(.+)', block)
        return [s.strip() for s in items[:3]]
    # Fallback: last numbered list
    all_numbered = re.findall(r'(?:^|\n)\d+[.)]\s*(.+)', text)
    if len(all_numbered) >= 2:
        return [s.strip() for s in all_numbered[-3:]]
    return []


async def _stream_to_text(chat: LlmChat, user_message: UserMessage) -> str:
    full_text = ""
    async for ev in chat.stream_message(user_message):
        if isinstance(ev, TextDelta):
            full_text += ev.content
        elif isinstance(ev, StreamDone):
            break
    return full_text


async def analyze_image_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)

    chat = LlmChat(
        api_key=GEMINI_API_KEY,
        session_id=str(uuid.uuid4()),
        system_message=system_prompt,
    ).with_model("gemini", "gemini-3-flash-preview")

    ext = Path(file_path).suffix.lower().lstrip('.')
    mime_type = MIME_IMAGE.get(ext, 'image/jpeg')

    image_file = FileContentWithMimeType(file_path=file_path, mime_type=mime_type)
    user_message = UserMessage(text=prompt, file_contents=[image_file])

    full_text = await _stream_to_text(chat, user_message)
    suggestions = _extract_suggestions(full_text)

    return {
        "type": "text",
        "content": full_text,
        "detections": [],
        "suggestions": suggestions if suggestions else [
            "Run object detection with YOLO26",
            "Analyze with instance segmentation",
            "Export analysis results",
        ],
    }


async def analyze_video_gemini(file_path: str, prompt: str) -> dict:
    system_prompt = _get_system_prompt(prompt)

    chat = LlmChat(
        api_key=GEMINI_API_KEY,
        session_id=str(uuid.uuid4()),
        system_message=system_prompt,
    ).with_model("gemini", "gemini-3-flash-preview")

    ext = Path(file_path).suffix.lower().lstrip('.')
    mime_type = MIME_VIDEO.get(ext, 'video/mp4')

    video_file = FileContentWithMimeType(file_path=file_path, mime_type=mime_type)
    user_message = UserMessage(text=prompt, file_contents=[video_file])

    full_text = await _stream_to_text(chat, user_message)
    suggestions = _extract_suggestions(full_text)

    return {
        "type": "text",
        "content": full_text,
        "detections": [],
        "suggestions": suggestions if suggestions else [
            "Run YOLO detection on video frames",
            "Analyze specific time segments",
            "Export frame-by-frame analysis",
        ],
    }
