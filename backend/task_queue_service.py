import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Optional


class TaskQueueConfigurationError(RuntimeError):
    pass


class TaskQueueEnqueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnqueuedTask:
    name: str
    already_exists: bool = False


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise TaskQueueConfigurationError(f"Missing {name}")
    return value


def _project_id() -> str:
    return (
        os.environ.get("VIDEO_TASKS_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or ""
    ).strip()


def _worker_base_url() -> str:
    return _required_env("VIDEO_WORKER_URL").rstrip("/")


def _task_id(uid: str, session_id: str, job_id: str) -> str:
    digest = hashlib.sha256(f"{uid}:{session_id}:{job_id}".encode("utf-8")).hexdigest()[:16]
    return f"video-{job_id[:32]}-{digest}".replace("_", "-")


def _dispatch_deadline_seconds() -> int:
    try:
        value = int(os.environ.get("VIDEO_TASKS_DISPATCH_DEADLINE_SECONDS", "1800"))
    except ValueError:
        value = 1800
    return max(60, min(1800, value))


def enqueue_video_job(
    *,
    uid: str,
    session_id: str,
    job_id: str,
    task_payload: Optional[dict[str, Any]] = None,
) -> EnqueuedTask:
    try:
        from google.api_core import exceptions as google_exceptions
        from google.cloud import tasks_v2
        from google.protobuf import duration_pb2
    except Exception as exc:
        raise TaskQueueConfigurationError("google-cloud-tasks is not installed") from exc

    project = _project_id()
    if not project:
        raise TaskQueueConfigurationError("Missing VIDEO_TASKS_PROJECT or GOOGLE_CLOUD_PROJECT")

    location = _required_env("VIDEO_TASKS_LOCATION")
    queue = _required_env("VIDEO_TASKS_QUEUE")
    service_account = _required_env("VIDEO_TASKS_SERVICE_ACCOUNT_EMAIL")
    worker_url = _worker_base_url()
    audience = os.environ.get("VIDEO_TASKS_OIDC_AUDIENCE", "").strip() or worker_url

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue)
    task_name = client.task_path(project, location, queue, _task_id(uid, session_id, job_id))
    body = {
        "uid": uid,
        "session_id": session_id,
        "job_id": job_id,
        **(task_payload or {}),
    }
    task = {
        "name": task_name,
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{worker_url}/api/internal/video-jobs/{job_id}/run",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body).encode("utf-8"),
            "oidc_token": {
                "service_account_email": service_account,
                "audience": audience,
            },
        },
        "dispatch_deadline": duration_pb2.Duration(seconds=_dispatch_deadline_seconds()),
    }

    try:
        created = client.create_task(request={"parent": parent, "task": task})
        return EnqueuedTask(name=created.name, already_exists=False)
    except google_exceptions.AlreadyExists:
        return EnqueuedTask(name=task_name, already_exists=True)
    except TaskQueueConfigurationError:
        raise
    except Exception as exc:
        raise TaskQueueEnqueueError(f"Could not enqueue video job {job_id}") from exc
