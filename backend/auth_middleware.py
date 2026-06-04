import base64
import json
import os
from pathlib import Path
from typing import Optional

import firebase_admin
from fastapi.responses import JSONResponse
from firebase_admin import auth, credentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent


def _resolve_service_account_path() -> Optional[Path]:
    configured = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        return path

    matches = sorted(PROJECT_ROOT.glob("*firebase-adminsdk*.json"))
    return matches[0] if matches else None


def _service_account_info() -> Optional[dict]:
    encoded = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON_B64")
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if encoded:
        raw = base64.b64decode(encoded).decode("utf-8")
    return json.loads(raw) if raw else None


def initialize_firebase_admin():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account_info = _service_account_info()
    if service_account_info:
        cred = credentials.Certificate(service_account_info)
        return firebase_admin.initialize_app(cred)

    service_account_path = _resolve_service_account_path()
    if not service_account_path or not service_account_path.exists():
        raise RuntimeError(
            "Firebase service account not found. Set FIREBASE_SERVICE_ACCOUNT_JSON_B64 "
            "or FIREBASE_SERVICE_ACCOUNT_PATH."
        )

    cred = credentials.Certificate(str(service_account_path))
    return firebase_admin.initialize_app(cred)


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        initialize_firebase_admin()

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "Missing authentication token"}, status_code=401)

        try:
            decoded = auth.verify_id_token(token)
        except Exception:
            return JSONResponse({"detail": "Invalid authentication token"}, status_code=401)

        request.state.uid = decoded["uid"]
        request.state.firebase_user = decoded
        return await call_next(request)
