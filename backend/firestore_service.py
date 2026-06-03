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
        "input_filename": payload["input_filename"],
        "output_url": payload.get("output_url"),
        "input_key": payload["input_key"],
        "output_key": payload.get("output_key"),
        "progress": payload.get("progress", 0),
        "error": payload.get("error"),
        "created_at": now,
        "updated_at": now,
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
