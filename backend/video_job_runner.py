import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import cv2
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from firestore_service import get_job, update_job, update_job_sync, utc_now_iso
from locate_service import MODEL_TYPE as LOCATE_MODEL_TYPE
from r2_service import download_file, upload_file
from session_service import add_message, set_session_video_status

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"done", "failed"}


class InternalAuthError(RuntimeError):
    pass


class VideoJobError(RuntimeError):
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code


def _storage_key(uid: str, session_id: str, job_id: str, kind: str, filename: str) -> str:
    return f"{kind}/{uid}/{session_id}/{job_id}/{filename}"


def _download_job_input(job: dict[str, Any], work_dir: Path) -> Path:
    input_key = job.get("input_key")
    if not input_key:
        raise VideoJobError("Input file not found.", "input_missing")
    suffix = Path(job.get("input_filename") or "input").suffix or ".bin"
    local_path = work_dir / f"input{suffix}"
    download_file(input_key, local_path)
    return local_path


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


def _assistant_message_id(job_id: str) -> str:
    return f"job-{job_id}-assistant"


def _build_progress_mongo_client(uid: str, job_id: str):
    class FakeCollection:
        def update_one(self, _filter, update):
            updates = dict(update.get("$set", update))
            if updates.get("status") == "done" and "output_url" not in updates:
                updates["status"] = "processing"
                updates["progress"] = min(int(updates.get("progress", 95)), 95)
            updates.setdefault("phase", "processing")
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


def verify_internal_video_request(authorization: str, shared_secret: Optional[str] = None) -> None:
    configured_secret = os.environ.get("VIDEO_INTERNAL_SHARED_SECRET", "").strip()
    if configured_secret:
        if shared_secret and shared_secret == configured_secret:
            return
        raise InternalAuthError("Invalid internal worker token")

    audience = os.environ.get("VIDEO_TASKS_OIDC_AUDIENCE", "").strip() or os.environ.get("VIDEO_WORKER_URL", "").strip()
    service_account = os.environ.get("VIDEO_TASKS_SERVICE_ACCOUNT_EMAIL", "").strip()
    if not audience or not service_account:
        raise InternalAuthError("Internal worker authentication is not configured")

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InternalAuthError("Missing Cloud Tasks OIDC token")

    try:
        claims = id_token.verify_oauth2_token(token, GoogleAuthRequest(), audience=audience)
    except Exception as exc:
        raise InternalAuthError("Invalid Cloud Tasks OIDC token") from exc

    email = claims.get("email") or claims.get("sub")
    if email != service_account:
        raise InternalAuthError("Cloud Tasks token has unexpected service account")


def _mark_done(uid: str, session_id: str, job_id: str, updates: dict[str, Any], model: str) -> None:
    update_job(
        uid,
        job_id,
        {
            **updates,
            "status": "done",
            "progress": 100,
            "phase": "done",
            "completed_unseen": True,
            "error": None,
            "user_message": None,
            "finished_at": utc_now_iso(),
        },
    )
    set_session_video_status(uid, session_id, "done", job_id=job_id, completed_unseen=True)

    suggestions = (
        ["Refine the target prompt", "Describe this video with Gemini", "Download result"]
        if model == LOCATE_MODEL_TYPE
        else ["Analyze frames with Gemini", "Run segmentation", "Download result"]
    )
    add_message(
        uid,
        session_id,
        {
            "message_id": _assistant_message_id(job_id),
            "role": "assistant",
            "content": "Processed video is ready.",
            "output_type": "video",
            "output_r2_path": updates.get("output_key"),
            "job_id": job_id,
            "model": model,
            "frames": updates.get("frames") or [],
            "suggestions": suggestions,
        },
    )


def _mark_failed(
    uid: str,
    session_id: str,
    job_id: str,
    model: str,
    message: str,
    error_code: Optional[str] = None,
) -> None:
    safe_message = (message or "Video processing failed. Please try again.")[:500]
    update_job(
        uid,
        job_id,
        {
            "status": "failed",
            "phase": "failed",
            "error": safe_message,
            "user_message": safe_message,
            "error_code": error_code,
            "progress": 100,
            "completed_unseen": True,
            "finished_at": utc_now_iso(),
        },
    )
    set_session_video_status(uid, session_id, "failed", job_id=job_id, completed_unseen=True)
    add_message(
        uid,
        session_id,
        {
            "message_id": _assistant_message_id(job_id),
            "role": "assistant",
            "content": safe_message,
            "output_type": "error",
            "job_id": job_id,
            "model": model,
        },
    )


def run_video_job(
    uid: str,
    session_id: str,
    job_id: str,
    task_retry_count: Optional[int] = None,
    task_execution_count: Optional[int] = None,
) -> dict[str, Any]:
    job = get_job(uid, job_id)
    if not job:
        raise VideoJobError("Job not found.", "job_missing")

    model = job.get("model")
    if job.get("status") in TERMINAL_STATUSES:
        return {"status": "already_terminal", "job_id": job_id}
    if job.get("status") == "processing":
        stored_execution_count = job.get("task_execution_count")
        if (
            task_execution_count is None
            or stored_execution_count is None
            or int(task_execution_count) <= int(stored_execution_count)
        ):
            return {"status": "already_processing", "job_id": job_id}

    update_job(
        uid,
        job_id,
        {
            "status": "processing",
            "phase": "downloading",
            "progress": max(1, int(job.get("progress") or 1)),
            "started_at": job.get("started_at") or utc_now_iso(),
            "task_retry_count": task_retry_count,
            "task_execution_count": task_execution_count,
        },
    )
    set_session_video_status(uid, session_id, "processing", job_id=job_id, completed_unseen=False)

    try:
        if model == LOCATE_MODEL_TYPE:
            return _run_locate_video_job(uid, session_id, job_id, job)
        return _run_yolo_video_job(uid, session_id, job_id, job)
    except Exception as exc:
        logger.error("Video job %s failed: %s", job_id, exc, exc_info=True)
        _mark_failed(uid, session_id, job_id, model or "video", str(exc), getattr(exc, "error_code", None))
        return {"status": "failed", "job_id": job_id}


def _run_locate_video_job(uid: str, session_id: str, job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    import locate_video_processor

    prompt = job.get("prompt") or "Analyze this video"
    with tempfile.TemporaryDirectory(prefix="deplyzegpt-locate-video-") as tmp:
        work_dir = Path(tmp)
        input_path = _download_job_input(job, work_dir)
        output_dir = work_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        def progress_callback(updates: dict[str, Any]):
            update_job_sync(uid, job_id, updates)

        result = locate_video_processor.process_video_locate(
            job_id,
            str(input_path),
            prompt,
            output_dir,
            progress_callback,
        )

        output_key = _storage_key(uid, session_id, job_id, "outputs", "output.mp4")
        upload_file(output_key, Path(result["output_path"]), "video/mp4")
        frames_for_firestore = result.get("frames", [])
        _mark_done(
            uid,
            session_id,
            job_id,
            {
                "frame_total": len(frames_for_firestore),
                "frame_completed": len(frames_for_firestore),
                "batch_total": result.get("batch_total"),
                "batch_completed": result.get("batch_total"),
                "sampling": result.get("sampling") or {},
                "frames": frames_for_firestore,
                "manifest_key": None,
                "output_key": output_key,
                "output_r2_path": output_key,
                "output_url": None,
                "backend": result.get("backend"),
                "batch_size": result.get("batch_size"),
            },
            LOCATE_MODEL_TYPE,
        )
        return {"status": "done", "job_id": job_id, "output_key": output_key}


def _run_yolo_video_job(uid: str, session_id: str, job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    import video_processor

    model_type = job.get("model")
    confidence = float(job.get("confidence") or 0.25)
    class_filter_ids = job.get("class_filter_ids")
    with tempfile.TemporaryDirectory(prefix="deplyzegpt-video-") as tmp:
        work_dir = Path(tmp)
        input_path = _download_job_input(job, work_dir)
        output_dir = work_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("MONGO_URL", "firestore-progress://local")
        os.environ.setdefault("DB_NAME", "deplyzegpt")
        video_processor.MongoClient = _build_progress_mongo_client(uid, job_id)

        duration_seconds = _get_video_duration_seconds(str(input_path))
        timeout_multiplier = 20 if model_type == "yolo26-sem" else 4
        timeout_floor = 1200 if model_type == "yolo26-sem" else 600
        timeout_seconds = max(timeout_floor, int(duration_seconds * timeout_multiplier))

        async def _process():
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
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

        output_path = asyncio.run(_process())
        output_key = _storage_key(uid, session_id, job_id, "outputs", "output.mp4")
        upload_file(output_key, Path(output_path), "video/mp4")
        _mark_done(
            uid,
            session_id,
            job_id,
            {
                "output_key": output_key,
                "output_r2_path": output_key,
                "output_url": None,
            },
            model_type,
        )
        return {"status": "done", "job_id": job_id, "output_key": output_key}
