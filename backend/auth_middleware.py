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


def _provider_ids(user_record) -> set[str]:
    return {
        getattr(provider, "provider_id", "")
        for provider in getattr(user_record, "provider_data", []) or []
        if getattr(provider, "provider_id", "")
    }


def _is_google_user(decoded: dict, user_record) -> bool:
    firebase_claims = decoded.get("firebase", {}) or {}
    if firebase_claims.get("sign_in_provider") == "google.com":
        return True
    return "google.com" in _provider_ids(user_record)


def _is_verified_for_app(decoded: dict, user_record) -> bool:
    if _is_google_user(decoded, user_record):
        return True
    return bool(getattr(user_record, "email_verified", False))


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        initialize_firebase_admin()

    async def dispatch(self, request: Request, call_next):
        if (
            request.method == "OPTIONS"
            or request.url.path == "/api/healthz"
            or not request.url.path.startswith("/api/")
        ):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "Missing authentication token"}, status_code=401)

        try:
            decoded = auth.verify_id_token(token)
        except Exception:
            return JSONResponse({"detail": "Invalid authentication token"}, status_code=401)

        try:
            user_record = auth.get_user(decoded["uid"])
        except Exception:
            return JSONResponse({"detail": "Invalid authentication token"}, status_code=401)

        if not _is_verified_for_app(decoded, user_record):
            return JSONResponse({"detail": "Email verification required"}, status_code=403)

        request.state.uid = decoded["uid"]
        request.state.firebase_user = decoded
        request.state.firebase_user_record = user_record
        return await call_next(request)
