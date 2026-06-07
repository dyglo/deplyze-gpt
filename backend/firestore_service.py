from datetime import datetime, timezone
from typing import Any, Dict, Optional

from firebase_admin import firestore

from auth_middleware import initialize_firebase_admin


JOB_SUBCOLLECTION = "items"

initialize_firebase_admin()
db = firestore.client()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_ref(uid: str, job_id: str):
    return db.collection("jobs").document(uid).collection(JOB_SUBCOLLECTION).document(job_id)


def create_job(uid: str, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now_iso()
    data = {
        "job_id": job_id,
        "uid": uid,
        "session_id": payload.get("session_id"),
        "model": payload.get("model"),
        "type": payload["type"],
        "status": payload.get("status", "uploaded"),
        "phase": payload.get("phase"),
        "input_filename": payload["input_filename"],
        "output_url": payload.get("output_url"),
        "input_key": payload["input_key"],
        "output_key": payload.get("output_key"),
        "progress": payload.get("progress", 0),
        "frame_total": payload.get("frame_total", 0),
        "frame_completed": payload.get("frame_completed", 0),
        "batch_total": payload.get("batch_total", 0),
        "batch_completed": payload.get("batch_completed", 0),
        "analysis_frame_cap": payload.get("analysis_frame_cap"),
        "target_p95_seconds": payload.get("target_p95_seconds"),
        "backend": payload.get("backend"),
        "batch_size": payload.get("batch_size"),
        "completed_unseen": payload.get("completed_unseen", False),
        "user_message": payload.get("user_message"),
        "error": payload.get("error"),
        "created_at": now,
        "updated_at": now,
        "queued_at": payload.get("queued_at"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "task_name": payload.get("task_name"),
        "task_retry_count": payload.get("task_retry_count"),
        "task_execution_count": payload.get("task_execution_count"),
    }
    job_ref(uid, job_id).set(data)
    return data


def get_job(uid: str, job_id: str) -> Optional[Dict[str, Any]]:
    snapshot = job_ref(uid, job_id).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def update_job(uid: str, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    data = {**updates, "updated_at": utc_now_iso()}
    job_ref(uid, job_id).update(data)
    return data


def update_job_sync(uid: str, job_id: str, updates: Dict[str, Any]) -> None:
    update_job(uid, job_id, updates)
