import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from auth_middleware import initialize_firebase_admin
from r2_service import bucket_name, get_r2_client


SESSION_SUBCOLLECTION = "items"
MESSAGE_SUBCOLLECTION = "messages"

initialize_firebase_admin()
db = firestore.client()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_name(value: Optional[str]) -> str:
    name = (value or "").strip()
    if not name:
        return "New analysis"
    return name[:80]


def name_from_context(filename: Optional[str] = None, prompt: Optional[str] = None) -> str:
    if filename:
        stem = Path(filename).stem.strip()
        if stem:
            return _clean_name(stem)
    return _clean_name(prompt)


def sessions_collection(uid: str):
    return db.collection("sessions").document(uid).collection(SESSION_SUBCOLLECTION)


def session_ref(uid: str, session_id: str):
    return sessions_collection(uid).document(session_id)


def messages_collection(uid: str, session_id: str):
    return session_ref(uid, session_id).collection(MESSAGE_SUBCOLLECTION)


def message_ref(uid: str, session_id: str, message_id: str):
    return messages_collection(uid, session_id).document(message_id)


def create_session(
    uid: str,
    name: Optional[str] = None,
    model: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = utc_now_iso()
    sid = session_id or str(uuid.uuid4())
    data = {
        "session_id": sid,
        "name": _clean_name(name),
        "model": model or "gemini",
        "pinned": False,
        "video_job_status": "none",
        "video_job_ids": [],
        "video_completed_unseen": False,
        "created_at": now,
        "updated_at": now,
    }
    session_ref(uid, sid).set(data)
    return data


def ensure_session(
    uid: str,
    session_id: Optional[str] = None,
    name: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    if session_id:
        snapshot = session_ref(uid, session_id).get()
        if snapshot.exists:
            return snapshot.to_dict()
    return create_session(uid, name=name, model=model, session_id=session_id)


def get_session(uid: str, session_id: str) -> Optional[Dict[str, Any]]:
    snapshot = session_ref(uid, session_id).get()
    return snapshot.to_dict() if snapshot.exists else None


def list_sessions(uid: str) -> List[Dict[str, Any]]:
    docs = sessions_collection(uid).stream()
    sessions = [doc.to_dict() for doc in docs]
    return sorted(
        sessions,
        key=lambda item: (bool(item.get("pinned")), item.get("updated_at", "")),
        reverse=True,
    )


def update_session(uid: str, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {}
    if "name" in updates and updates["name"] is not None:
        allowed["name"] = _clean_name(updates["name"])
    if "pinned" in updates and updates["pinned"] is not None:
        allowed["pinned"] = bool(updates["pinned"])
    if "model" in updates and updates["model"] is not None:
        allowed["model"] = updates["model"]
    if not allowed:
        current = get_session(uid, session_id)
        if current is None:
            raise ValueError("Session not found")
        return current
    allowed["updated_at"] = utc_now_iso()
    session_ref(uid, session_id).update(allowed)
    current = get_session(uid, session_id)
    if current is None:
        raise ValueError("Session not found")
    return current


def touch_session(uid: str, session_id: str, model: Optional[str] = None) -> None:
    updates = {"updated_at": utc_now_iso()}
    if model:
        updates["model"] = model
    session_ref(uid, session_id).update(updates)


def set_session_video_status(
    uid: str,
    session_id: str,
    status: str,
    job_id: Optional[str] = None,
    completed_unseen: Optional[bool] = None,
) -> None:
    updates: Dict[str, Any] = {
        "video_job_status": status,
        "updated_at": utc_now_iso(),
    }
    if job_id:
        updates["video_job_ids"] = firestore.ArrayUnion([job_id])
    if completed_unseen is not None:
        updates["video_completed_unseen"] = bool(completed_unseen)
    session_ref(uid, session_id).update(updates)


def clear_session_video_unseen(uid: str, session_id: str) -> Dict[str, Any]:
    session_ref(uid, session_id).update(
        {
            "video_completed_unseen": False,
            "updated_at": utc_now_iso(),
        }
    )
    current = get_session(uid, session_id)
    if current is None:
        raise ValueError("Session not found")
    return current


def add_message(uid: str, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now_iso()
    message_id = payload.get("message_id") or str(uuid.uuid4())
    data = {
        "message_id": message_id,
        "role": payload["role"],
        "content": payload.get("content") or "",
        "input_filename": payload.get("input_filename"),
        "input_r2_path": payload.get("input_r2_path"),
        "output_r2_path": payload.get("output_r2_path"),
        "manifest_r2_path": payload.get("manifest_r2_path"),
        "output_type": payload.get("output_type"),
        "job_id": payload.get("job_id"),
        "model": payload.get("model"),
        "detections": payload.get("detections") or [],
        "frames": payload.get("frames") or [],
        "suggestions": payload.get("suggestions") or [],
        "created_at": now,
    }
    message_ref(uid, session_id, message_id).set(data)
    touch_session(uid, session_id, payload.get("model"))
    return data


def list_messages(uid: str, session_id: str) -> List[Dict[str, Any]]:
    docs = messages_collection(uid, session_id).order_by("created_at").stream()
    return [doc.to_dict() for doc in docs]


def _delete_collection(collection_ref, batch_size: int = 100) -> None:
    while True:
        docs = list(collection_ref.limit(batch_size).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()


def _delete_r2_prefix(prefix: str) -> None:
    client = get_r2_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name(), Prefix=prefix):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket_name(), Delete={"Objects": objects})


def delete_session(uid: str, session_id: str) -> None:
    _delete_collection(messages_collection(uid, session_id))
    _delete_collection(
        db.collection("jobs").document(uid).collection("items").where(
            filter=FieldFilter("session_id", "==", session_id)
        )
    )
    _delete_r2_prefix(f"uploads/{uid}/{session_id}/")
    _delete_r2_prefix(f"outputs/{uid}/{session_id}/")
    session_ref(uid, session_id).delete()
