from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import uuid
import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from urllib.parse import quote
from pydantic import BaseModel
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import cv2

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth_middleware import FirebaseAuthMiddleware
from firestore_service import create_job, get_job, update_job, update_job_sync
from r2_service import upload_bytes, upload_file, upload_fileobj, download_file, get_object, presigned_get_url
from session_service import (
    add_message,
    delete_session,
    ensure_session,
    get_session,
    list_messages,
    list_sessions,
    name_from_context,
    update_session,
)
from gemini_service import GeminiServiceError
from locate_service import MODEL_TYPE as LOCATE_MODEL_TYPE, LocateServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="DeplyzeGPT API")
api_router = APIRouter(prefix="/api")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://vision-sys.web.app",
    "https://vision-sys.firebaseapp.com",
    "https://deplyzegpt.xyz",
]


def _cors_origins() -> list[str]:
    configured = os.environ.get("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or DEFAULT_CORS_ORIGINS


class ImageAnalysisRequest(BaseModel):
    file_url: str
    model: str
    prompt: str = "Analyze this image in detail"
    confidence: float = 0.25
    session_id: Optional[str] = None


class VideoAnalysisRequest(BaseModel):
    file_url: str
    model: str
    confidence: float = 0.25
    prompt: str = "Analyze this video"
    session_id: Optional[str] = None


class VideoGeminiRequest(BaseModel):
    file_url: str
    prompt: str = "Describe what is happening in this video"
    session_id: Optional[str] = None


class SessionCreateRequest(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    filename: Optional[str] = None
    model: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    name: Optional[str] = None
    pinned: Optional[bool] = None


def _uid(request: Request) -> str:
    uid = getattr(request.state, "uid", None)
    if not uid:
        raise HTTPException(401, "Missing authenticated user")
    return uid


def _storage_key(uid: str, session_id: str, job_id: str, kind: str, filename: str) -> str:
    return f"{kind}/{uid}/{session_id}/{job_id}/{filename}"


def _download_url_for_output_key(key: str) -> Optional[str]:
    parts = key.split("/")
    if len(parts) != 5 or parts[0] != "outputs":
        return None
    _, _uid_value, session_id, job_id, filename = parts
    return (
        "/api/files/download/output/"
        f"{quote(session_id, safe='')}/"
        f"{quote(job_id, safe='')}/"
        f"{quote(filename, safe='')}"
    )


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _frames_with_fresh_urls(frames: list[dict] | None) -> list[dict]:
    refreshed = []
    for frame in frames or []:
        data = dict(frame)
        key = data.get("r2_path") or data.get("key")
        if key:
            data["url"] = presigned_get_url(key)
            data["download_url"] = _download_url_for_output_key(key)
        refreshed.append(data)
    return refreshed


def _job_with_fresh_urls(job: dict) -> dict:
    data = dict(job)
    if data.get("frames"):
        data["frames"] = _frames_with_fresh_urls(data.get("frames"))
    output_key = data.get("output_key") or data.get("output_r2_path")
    if output_key:
        data["output_url"] = presigned_get_url(output_key)
        data["output_download_url"] = _download_url_for_output_key(output_key)
    if data.get("manifest_key"):
        data["manifest_url"] = presigned_get_url(data["manifest_key"])
    return data


def _job_id_from_file_url(file_url: str) -> Optional[str]:
    marker = "/api/files/uploads/"
    if marker not in file_url:
        return None
    remainder = file_url.split(marker, 1)[1].strip("/")
    parts = remainder.split("/")
    return parts[0] if parts else None


def _get_video_duration_seconds(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if frame_count <= 0 or fps <= 0:
            return 0.0
        return frame_count / fps
    finally:
        cap.release()


def _require_job(uid: str, job_id: str) -> dict:
    job = get_job(uid, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _require_session(uid: str, session_id: str) -> dict:
    session = get_session(uid, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


def _message_with_fresh_urls(message: dict) -> dict:
    data = dict(message)
    if data.get("input_r2_path"):
        data["input_url"] = presigned_get_url(data["input_r2_path"])
    if data.get("output_r2_path"):
        data["output_url"] = presigned_get_url(data["output_r2_path"])
        data["output_download_url"] = _download_url_for_output_key(data["output_r2_path"])
    if data.get("frames"):
        data["frames"] = _frames_with_fresh_urls(data.get("frames"))
    if data.get("manifest_r2_path"):
        data["manifest_url"] = presigned_get_url(data["manifest_r2_path"])
    return data


def _attachment_filename(key: str) -> str:
    filename = Path(key).name or "deplyzegpt_output"
    return "".join(ch for ch in filename if ch.isalnum() or ch in "._-") or "deplyzegpt_output"


def _stream_r2_body(body):
    try:
        for chunk in body.iter_chunks(chunk_size=1024 * 1024):
            if chunk:
                yield chunk
    finally:
        body.close()


def _stream_output_key(key: str, log_context: str):
    try:
        obj = get_object(key)
    except Exception as e:
        logger.warning("R2 download failed for %s: %s", log_context, e)
        raise HTTPException(404, "Output file not found")

    body = obj["Body"]
    headers = {
        "Content-Disposition": f'attachment; filename="{_attachment_filename(key)}"',
    }
    if obj.get("ContentLength") is not None:
        headers["Content-Length"] = str(obj["ContentLength"])

    return StreamingResponse(
        _stream_r2_body(body),
        media_type=obj.get("ContentType") or "application/octet-stream",
        headers=headers,
    )


def _download_job_input(uid: str, job_id: str, work_dir: Path) -> Tuple[Path, dict]:
    job = _require_job(uid, job_id)
    input_key = job.get("input_key")
    if not input_key:
        raise HTTPException(404, "Input file not found")

    suffix = Path(job.get("input_filename") or "input").suffix or ".bin"
    local_path = work_dir / f"input{suffix}"
    download_file(input_key, local_path)
    return local_path, job


def _decode_data_uri(data_uri: str) -> Tuple[bytes, str]:
    if "," not in data_uri:
        raise ValueError("Invalid data URI")
    header, encoded = data_uri.split(",", 1)
    content_type = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        content_type = header[5:].split(";", 1)[0]
    return base64.b64decode(encoded), content_type


def _build_progress_mongo_client(uid: str, job_id: str):
    class FakeCollection:
        def update_one(self, _filter, update):
            updates = dict(update.get("$set", update))
            if updates.get("status") == "done" and "output_url" not in updates:
                updates["status"] = "processing"
                updates["progress"] = min(int(updates.get("progress", 95)), 95)
            update_job_sync(uid, job_id, updates)

    class FakeDatabase:
        video_jobs = FakeCollection()

    class FakeMongoClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __getitem__(self, _name):
            return FakeDatabase()

        def close(self):
            pass

    return FakeMongoClient


@api_router.get("/")
async def root():
    return {"message": "DeplyzeGPT API", "status": "ok"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@api_router.get("/healthz")
async def api_healthz():
    return {"status": "ok"}


@api_router.post("/sessions")
async def create_session_route(request: Request, payload: SessionCreateRequest):
    uid = _uid(request)
    name = payload.name or name_from_context(payload.filename, payload.prompt)
    return ensure_session(uid, name=name, model=payload.model)


@api_router.get("/sessions")
async def list_sessions_route(request: Request):
    return {"sessions": list_sessions(_uid(request))}


@api_router.patch("/sessions/{session_id}")
async def update_session_route(request: Request, session_id: str, payload: SessionUpdateRequest):
    uid = _uid(request)
    _require_session(uid, session_id)
    return update_session(uid, session_id, payload.model_dump(exclude_unset=True))


@api_router.delete("/sessions/{session_id}")
async def delete_session_route(request: Request, session_id: str):
    uid = _uid(request)
    _require_session(uid, session_id)
    delete_session(uid, session_id)
    return {"status": "deleted"}


@api_router.get("/sessions/{session_id}/messages")
async def list_session_messages_route(request: Request, session_id: str):
    uid = _uid(request)
    _require_session(uid, session_id)
    messages = [_message_with_fresh_urls(message) for message in list_messages(uid, session_id)]
    return {"messages": messages}


@api_router.post("/upload")
async def upload_file_route(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    uid = _uid(request)
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)

    if size > 100 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 100MB limit")

    ct = file.content_type or ""
    fname = file.filename or "upload"
    ext = Path(fname).suffix.lower()

    is_image = ct.startswith("image/") or ext in [".jpg", ".jpeg", ".png", ".webp"]
    is_video = ct.startswith("video/") or ext in [".mp4", ".mov", ".avi"]

    if not (is_image or is_video):
        raise HTTPException(400, "Unsupported file type. Only image/video files accepted.")

    session = ensure_session(
        uid,
        session_id=session_id,
        name=name_from_context(filename=fname),
        model=None,
    )
    session_id = session["session_id"]
    job_id = str(uuid.uuid4())
    safe_ext = ext if ext else (".jpg" if is_image else ".mp4")
    input_filename = f"input{safe_ext}"
    input_key = _storage_key(uid, session_id, job_id, "uploads", input_filename)

    upload_fileobj(input_key, file.file, ct or None)
    create_job(
        uid,
        job_id,
        {
            "type": "image" if is_image else "video",
            "status": "uploaded",
            "input_filename": fname,
            "input_key": input_key,
            "session_id": session_id,
        },
    )

    return {
        "session_id": session_id,
        "file_id": job_id,
        "url": f"/api/files/uploads/{job_id}/{input_filename}",
        "filename": fname,
        "file_type": "image" if is_image else "video",
        "size": size,
        "content_type": ct,
    }


@api_router.get("/files/{file_type}/{job_id}/{filename}")
async def serve_r2_file(request: Request, file_type: str, job_id: str, filename: str):
    uid = _uid(request)
    job = _require_job(uid, job_id)

    if file_type == "uploads":
        key = job.get("input_key")
    elif file_type == "outputs":
        key = job.get("output_key")
    else:
        raise HTTPException(404, "Invalid file type")

    if not key:
        raise HTTPException(404, "File not found")

    return RedirectResponse(presigned_get_url(key), status_code=307)


@api_router.get("/files/presign/{job_id}")
async def presign_output_file(request: Request, job_id: str):
    uid = _uid(request)
    job = _require_job(uid, job_id)
    output_key = job.get("output_key")
    if not output_key:
        raise HTTPException(404, "Output file not ready")
    return {"url": presigned_get_url(output_key), "expires_in": 3600}


@api_router.get("/files/download/{job_id}")
async def download_output_file(request: Request, job_id: str):
    uid = _uid(request)
    job = _require_job(uid, job_id)
    output_key = job.get("output_key")
    if not output_key:
        raise HTTPException(404, "Output file not ready")

    return _stream_output_key(output_key, f"job {job_id}")


@api_router.get("/files/download/output/{session_id}/{job_id}/{filename}")
async def download_output_file_by_path(request: Request, session_id: str, job_id: str, filename: str):
    uid = _uid(request)
    _require_session(uid, session_id)
    output_key = _storage_key(uid, session_id, job_id, "outputs", _attachment_filename(filename))
    return _stream_output_key(output_key, f"session {session_id} job {job_id}")


@api_router.get("/files/{file_type}/{filename}")
async def serve_legacy_file(file_type: str, filename: str):
    raise HTTPException(404, "Legacy local file URLs are no longer supported")


@api_router.post("/analyze/image")
async def analyze_image(request: Request, payload: ImageAnalysisRequest):
    uid = _uid(request)
    job_id = _job_id_from_file_url(payload.file_url)
    if not job_id:
        raise HTTPException(400, "Invalid upload reference")

    job = _require_job(uid, job_id)
    session_id = payload.session_id or job.get("session_id")
    session = ensure_session(
        uid,
        session_id=session_id,
        name=name_from_context(job.get("input_filename"), payload.prompt),
        model=payload.model,
    )
    session_id = session["session_id"]
    if job.get("session_id") != session_id:
        update_job(uid, job_id, {"session_id": session_id})

    update_job(uid, job_id, {"status": "processing", "model": payload.model, "progress": 10})
    add_message(
        uid,
        session_id,
        {
            "role": "user",
            "content": payload.prompt,
            "input_filename": job.get("input_filename"),
            "input_r2_path": job.get("input_key"),
            "job_id": job_id,
            "model": payload.model,
        },
    )

    class_filter_ids = None
    if payload.model not in {"gemini", LOCATE_MODEL_TYPE}:
        from yolo_service import ClassFilterError, resolve_class_filter

        try:
            loop = asyncio.get_event_loop()
            class_filter = await loop.run_in_executor(executor, resolve_class_filter, payload.prompt, payload.model)
            class_filter_ids = class_filter.ids if class_filter else None
        except ClassFilterError as e:
            message = str(e)
            update_job(uid, job_id, {"status": "failed", "progress": 100, "error": message[:500]})
            add_message(
                uid,
                session_id,
                {
                    "role": "assistant",
                    "content": message,
                    "output_type": "error",
                    "job_id": job_id,
                    "model": payload.model,
                },
            )
            raise HTTPException(422, message)
        except FileNotFoundError as e:
            update_job(uid, job_id, {"status": "failed", "error": str(e)[:500]})
            raise HTTPException(404, str(e))
        except Exception as e:
            update_job(uid, job_id, {"status": "failed", "error": str(e)[:500]})
            logger.error("Class filter resolution failed: %s", e, exc_info=True)
            raise HTTPException(500, "Analysis failed. Please try again.")

    with tempfile.TemporaryDirectory(prefix="deplyzegpt-image-") as tmp:
        filepath, _job = _download_job_input(uid, job_id, Path(tmp))
        try:
            if payload.model == "gemini":
                from gemini_service import analyze_image_gemini
                result = await analyze_image_gemini(str(filepath), payload.prompt)
                update_job(uid, job_id, {"status": "done", "progress": 100, "output_url": None})
                add_message(
                    uid,
                    session_id,
                    {
                        "role": "assistant",
                        "content": result.get("content", ""),
                        "output_type": "text",
                        "job_id": job_id,
                        "model": payload.model,
                        "suggestions": result.get("suggestions", []),
                    },
                )
                result["session_id"] = session_id
                result["job_id"] = job_id
                return result

            if payload.model == LOCATE_MODEL_TYPE:
                from locate_service import analyze_image_locate
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(executor, analyze_image_locate, str(filepath), payload.prompt)
                image_bytes, content_type = _decode_data_uri(result["content"])
                output_key = _storage_key(uid, session_id, job_id, "outputs", "output.jpg")
                upload_bytes(output_key, image_bytes, content_type)
                output_url = presigned_get_url(output_key)
                update_job(
                    uid,
                    job_id,
                    {
                        "status": "done",
                        "progress": 100,
                        "output_key": output_key,
                        "output_r2_path": output_key,
                        "output_url": None,
                    },
                )
                add_message(
                    uid,
                    session_id,
                    {
                        "role": "assistant",
                        "content": "Image grounding complete.",
                        "output_type": "image",
                        "output_r2_path": output_key,
                        "job_id": job_id,
                        "model": payload.model,
                        "detections": result.get("detections", []),
                        "suggestions": result.get("suggestions", []),
                    },
                )
                result["content"] = output_url
                result["download_url"] = _download_url_for_output_key(output_key)
                result["job_id"] = job_id
                result["session_id"] = session_id
                return result

            from yolo_service import analyze_image_yolo
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor, analyze_image_yolo, str(filepath), payload.model, payload.confidence, class_filter_ids
            )
            image_bytes, content_type = _decode_data_uri(result["content"])
            output_key = _storage_key(uid, session_id, job_id, "outputs", "output.jpg")
            upload_bytes(output_key, image_bytes, content_type)
            output_url = presigned_get_url(output_key)
            update_job(
                uid,
                job_id,
                {
                    "status": "done",
                    "progress": 100,
                    "output_key": output_key,
                    "output_r2_path": output_key,
                    "output_url": None,
                },
            )
            add_message(
                uid,
                session_id,
                {
                    "role": "assistant",
                    "content": "Image analysis complete.",
                    "output_type": "image",
                    "output_r2_path": output_key,
                    "job_id": job_id,
                    "model": payload.model,
                    "detections": result.get("detections", []),
                    "suggestions": result.get("suggestions", []),
                },
            )
            result["content"] = output_url
            result["download_url"] = _download_url_for_output_key(output_key)
            result["job_id"] = job_id
            result["session_id"] = session_id
            return result
        except FileNotFoundError as e:
            update_job(uid, job_id, {"status": "failed", "error": str(e)[:500]})
            raise HTTPException(404, str(e))
        except LocateServiceError as e:
            message = str(e)
            update_job(uid, job_id, {"status": "failed", "error": message[:500]})
            raise HTTPException(getattr(e, "status_code", 503), message)
        except GeminiServiceError as e:
            message = str(e)
            update_job(uid, job_id, {"status": "failed", "error": message})
            raise HTTPException(503, message)
        except Exception as e:
            update_job(uid, job_id, {"status": "failed", "error": str(e)[:500]})
            logger.error("Image analysis error: %s", e, exc_info=True)
            raise HTTPException(500, "Analysis failed. Please try again.")


@api_router.post("/analyze/video")
async def analyze_video(request: Request, payload: VideoAnalysisRequest, background_tasks: BackgroundTasks):
    uid = _uid(request)
    if payload.model == "gemini":
        raise HTTPException(400, "Use /api/analyze/video/gemini for Gemini video analysis")

    job_id = _job_id_from_file_url(payload.file_url)
    if not job_id:
        raise HTTPException(400, "Invalid upload reference")

    job = _require_job(uid, job_id)
    if job.get("type") != "video":
        raise HTTPException(400, "Uploaded file is not a video")
    session_id = payload.session_id or job.get("session_id")
    session = ensure_session(
        uid,
        session_id=session_id,
        name=name_from_context(job.get("input_filename"), payload.prompt),
        model=payload.model,
    )
    session_id = session["session_id"]
    if job.get("session_id") != session_id:
        update_job(uid, job_id, {"session_id": session_id})

    if payload.model == LOCATE_MODEL_TYPE:
        if not _truthy_env("ENABLE_LOCATE_ANYTHING_VIDEO"):
            raise HTTPException(422, "LocateAnything video analysis is not enabled in this environment.")

        import locate_video_processor

        with tempfile.TemporaryDirectory(prefix="deplyzegpt-locate-video-preflight-") as tmp:
            input_path, _job = _download_job_input(uid, job_id, Path(tmp))
            duration_seconds = _get_video_duration_seconds(str(input_path))
            try:
                locate_video_processor.validate_video_duration(duration_seconds)
            except locate_video_processor.LocateVideoError as e:
                message = str(e)
                update_job(
                    uid,
                    job_id,
                    {
                        "status": "failed",
                        "model": payload.model,
                        "type": "video",
                        "progress": 100,
                        "phase": "failed",
                        "output_url": None,
                        "error": message[:500],
                        "session_id": session_id,
                    },
                )
                raise HTTPException(getattr(e, "status_code", 422), message)

        add_message(
            uid,
            session_id,
            {
                "role": "user",
                "content": payload.prompt,
                "input_filename": job.get("input_filename"),
                "input_r2_path": job.get("input_key"),
                "job_id": job_id,
                "model": payload.model,
            },
        )
        update_job(
            uid,
            job_id,
            {
                "status": "queued",
                "model": payload.model,
                "type": "video",
                "progress": 0,
                "phase": "queued",
                "frame_total": 0,
                "frame_completed": 0,
                "sampling": {"duration_seconds": round(duration_seconds, 3)},
                "frames": [],
                "output_url": None,
                "error": None,
                "session_id": session_id,
            },
        )
        background_tasks.add_task(_run_locate_video_job, uid, session_id, job_id, payload.prompt)
        return {"job_id": job_id, "session_id": session_id}

    from yolo_service import ClassFilterError, MODEL_MAP, ensure_model_available, resolve_class_filter
    if payload.model not in MODEL_MAP:
        raise HTTPException(422, f"Unsupported video model: {payload.model}")
    try:
        await asyncio.get_event_loop().run_in_executor(executor, ensure_model_available, payload.model)
    except Exception:
        raise HTTPException(
            422,
            f"Model {payload.model} could not be downloaded for video processing. Try again later.",
        )

    add_message(
        uid,
        session_id,
        {
            "role": "user",
            "content": payload.prompt,
            "input_filename": job.get("input_filename"),
            "input_r2_path": job.get("input_key"),
            "job_id": job_id,
            "model": payload.model,
        },
    )

    try:
        class_filter = await asyncio.get_event_loop().run_in_executor(
            executor, resolve_class_filter, payload.prompt, payload.model
        )
        class_filter_ids = class_filter.ids if class_filter else None
    except ClassFilterError as e:
        message = str(e)
        update_job(
            uid,
            job_id,
            {
                "status": "failed",
                "model": payload.model,
                "type": "video",
                "progress": 100,
                "output_url": None,
                "error": message[:500],
                "session_id": session_id,
            },
        )
        add_message(
            uid,
            session_id,
            {
                "role": "assistant",
                "content": message,
                "output_type": "error",
                "job_id": job_id,
                "model": payload.model,
            },
        )
        raise HTTPException(422, message)
    except Exception as e:
        message = "Analysis failed. Please try again."
        update_job(
            uid,
            job_id,
            {
                "status": "failed",
                "model": payload.model,
                "type": "video",
                "progress": 100,
                "output_url": None,
                "error": str(e)[:500],
                "session_id": session_id,
            },
        )
        add_message(
            uid,
            session_id,
            {
                "role": "assistant",
                "content": message,
                "output_type": "error",
                "job_id": job_id,
                "model": payload.model,
            },
        )
        logger.error("Video class filter resolution failed: %s", e, exc_info=True)
        raise HTTPException(500, message)

    update_job(
        uid,
        job_id,
        {
            "status": "queued",
            "model": payload.model,
            "type": "video",
            "progress": 0,
            "output_url": None,
            "error": None,
            "session_id": session_id,
        },
    )

    background_tasks.add_task(_run_video_job, uid, session_id, job_id, payload.model, payload.confidence, class_filter_ids)
    return {"job_id": job_id, "session_id": session_id}


@api_router.get("/analyze/video/status/{job_id}")
async def get_video_status(request: Request, job_id: str):
    return _job_with_fresh_urls(_require_job(_uid(request), job_id))


@api_router.post("/analyze/video/gemini")
async def analyze_video_gemini_route(request: Request, payload: VideoGeminiRequest):
    uid = _uid(request)
    job_id = _job_id_from_file_url(payload.file_url)
    if not job_id:
        raise HTTPException(400, "Invalid upload reference")

    job = _require_job(uid, job_id)
    session_id = payload.session_id or job.get("session_id")
    session = ensure_session(
        uid,
        session_id=session_id,
        name=name_from_context(job.get("input_filename"), payload.prompt),
        model="gemini",
    )
    session_id = session["session_id"]
    update_job(uid, job_id, {"status": "processing", "model": "gemini", "type": "video", "progress": 10, "session_id": session_id})
    add_message(
        uid,
        session_id,
        {
            "role": "user",
            "content": payload.prompt,
            "input_filename": job.get("input_filename"),
            "input_r2_path": job.get("input_key"),
            "job_id": job_id,
            "model": "gemini",
        },
    )

    with tempfile.TemporaryDirectory(prefix="deplyzegpt-gemini-video-") as tmp:
        filepath, _job = _download_job_input(uid, job_id, Path(tmp))
        try:
            from gemini_service import analyze_video_gemini
            result = await analyze_video_gemini(str(filepath), payload.prompt)
            update_job(uid, job_id, {"status": "done", "progress": 100, "output_url": None})
            add_message(
                uid,
                session_id,
                {
                    "role": "assistant",
                    "content": result.get("content", ""),
                    "output_type": "text",
                    "job_id": job_id,
                    "model": "gemini",
                    "suggestions": result.get("suggestions", []),
                },
            )
            result["session_id"] = session_id
            result["job_id"] = job_id
            return result
        except GeminiServiceError as e:
            message = str(e)
            update_job(uid, job_id, {"status": "failed", "error": message})
            raise HTTPException(503, message)
        except Exception as e:
            update_job(uid, job_id, {"status": "failed", "error": str(e)[:500]})
            logger.error("Gemini video error: %s", e, exc_info=True)
            raise HTTPException(500, "Analysis failed. Please try again.")


async def _run_locate_video_job(uid: str, session_id: str, job_id: str, prompt: str):
    with tempfile.TemporaryDirectory(prefix="deplyzegpt-locate-video-") as tmp:
        work_dir = Path(tmp)
        try:
            import locate_video_processor

            input_path, _job = _download_job_input(uid, job_id, work_dir)
            output_dir = work_dir / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)

            def progress_callback(updates: dict):
                update_job_sync(uid, job_id, updates)

            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    locate_video_processor.process_video_locate,
                    job_id,
                    str(input_path),
                    prompt,
                    output_dir,
                    progress_callback,
                ),
                timeout=locate_video_processor.job_timeout_seconds(),
            )

            output_key = _storage_key(uid, session_id, job_id, "outputs", "output.mp4")
            upload_file(output_key, Path(result["output_path"]), "video/mp4")
            frames_for_firestore = result.get("frames", [])

            update_job(
                uid,
                job_id,
                {
                    "status": "done",
                    "progress": 100,
                    "phase": "done",
                    "frame_total": len(frames_for_firestore),
                    "frame_completed": len(frames_for_firestore),
                    "sampling": result.get("sampling") or {},
                    "frames": frames_for_firestore,
                    "manifest_key": None,
                    "output_key": output_key,
                    "output_r2_path": output_key,
                    "output_url": None,
                    "error": None,
                },
            )
            add_message(
                uid,
                session_id,
                {
                    "role": "assistant",
                    "content": "Processed video is ready.",
                    "output_type": "video",
                    "output_r2_path": output_key,
                    "job_id": job_id,
                    "model": LOCATE_MODEL_TYPE,
                    "frames": frames_for_firestore,
                    "suggestions": ["Refine the target prompt", "Describe this video with Gemini", "Download result"],
                },
            )
        except asyncio.TimeoutError:
            message = "LocateAnything video processing timeout exceeded"
            update_job(uid, job_id, {"status": "failed", "phase": "failed", "error": message, "progress": 100})
            add_message(uid, session_id, {"role": "assistant", "content": message, "output_type": "error", "job_id": job_id, "model": LOCATE_MODEL_TYPE})
        except Exception as e:
            logger.error("Locate video job %s failed: %s", job_id, e, exc_info=True)
            message = str(e)[:500]
            update_job(uid, job_id, {"status": "failed", "phase": "failed", "error": message, "progress": 100})
            add_message(uid, session_id, {"role": "assistant", "content": message, "output_type": "error", "job_id": job_id, "model": LOCATE_MODEL_TYPE})


async def _run_video_job(uid: str, session_id: str, job_id: str, model_type: str, confidence: float, class_filter_ids=None):
    with tempfile.TemporaryDirectory(prefix="deplyzegpt-video-") as tmp:
        work_dir = Path(tmp)
        try:
            import video_processor

            input_path, _job = _download_job_input(uid, job_id, work_dir)
            output_dir = work_dir / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)

            os.environ.setdefault("MONGO_URL", "firestore-progress://local")
            os.environ.setdefault("DB_NAME", "deplyzegpt")
            video_processor.MongoClient = _build_progress_mongo_client(uid, job_id)

            loop = asyncio.get_event_loop()
            duration_seconds = _get_video_duration_seconds(str(input_path))
            timeout_multiplier = 20 if model_type == "yolo26-sem" else 4
            timeout_floor = 1200 if model_type == "yolo26-sem" else 600
            timeout_seconds = max(timeout_floor, int(duration_seconds * timeout_multiplier))
            output_path = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    video_processor.process_video_yolo,
                    job_id,
                    str(input_path),
                    model_type,
                    confidence,
                    output_dir,
                    class_filter_ids,
                ),
                timeout=timeout_seconds,
            )

            output_key = _storage_key(uid, session_id, job_id, "outputs", "output.mp4")
            upload_file(output_key, Path(output_path), "video/mp4")
            update_job(
                uid,
                job_id,
                {
                    "status": "done",
                    "progress": 100,
                    "output_key": output_key,
                    "output_r2_path": output_key,
                    "output_url": None,
                    "error": None,
                },
            )
            add_message(
                uid,
                session_id,
                {
                    "role": "assistant",
                    "content": "Processed video is ready.",
                    "output_type": "video",
                    "output_r2_path": output_key,
                    "job_id": job_id,
                    "model": model_type,
                    "suggestions": ["Analyze frames with Gemini", "Run segmentation", "Download result"],
                },
            )
        except asyncio.TimeoutError:
            message = "Processing timeout exceeded"
            update_job(uid, job_id, {"status": "failed", "error": message})
            add_message(uid, session_id, {"role": "assistant", "content": message, "output_type": "error", "job_id": job_id, "model": model_type})
        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e, exc_info=True)
            message = str(e)[:500]
            update_job(uid, job_id, {"status": "failed", "error": message})
            add_message(uid, session_id, {"role": "assistant", "content": message, "output_type": "error", "job_id": job_id, "model": model_type})


async def _prewarm_models():
    """Load YOLO models into memory at startup to avoid first-request cold start."""
    loop = asyncio.get_event_loop()
    for model_type in ["yolo26", "yolo26-seg"]:
        try:
            from yolo_service import get_model
            await loop.run_in_executor(executor, get_model, model_type)
            logger.info("Pre-warmed YOLO model: %s", model_type)
        except Exception as e:
            logger.warning("Pre-warm skipped for %s: %s", model_type, e)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_prewarm_models())
    logger.info("DeplyzeGPT API started")


app.include_router(api_router)

app.add_middleware(FirebaseAuthMiddleware)

cors_origins = _cors_origins()

app = CORSMiddleware(
    app=app,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
