import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth_middleware


def user_record(email_verified=False, providers=None):
    return SimpleNamespace(
        email_verified=email_verified,
        provider_data=[SimpleNamespace(provider_id=provider) for provider in (providers or ["password"])],
    )


def test_verified_password_user_passes_app_gate():
    decoded = {"uid": "user-1", "firebase": {"sign_in_provider": "password"}}

    assert auth_middleware._is_verified_for_app(decoded, user_record(email_verified=True))


def test_unverified_password_user_fails_app_gate():
    decoded = {"uid": "user-1", "firebase": {"sign_in_provider": "password"}}

    assert not auth_middleware._is_verified_for_app(decoded, user_record(email_verified=False))


def test_google_user_passes_app_gate_without_password_verification():
    decoded = {"uid": "user-1", "firebase": {"sign_in_provider": "google.com"}}

    assert auth_middleware._is_verified_for_app(decoded, user_record(email_verified=False, providers=["google.com"]))


def test_middleware_rejects_unverified_password_user(monkeypatch):
    monkeypatch.setattr(auth_middleware, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_middleware.auth,
        "verify_id_token",
        lambda token: {"uid": "user-1", "firebase": {"sign_in_provider": "password"}},
    )
    monkeypatch.setattr(auth_middleware.auth, "get_user", lambda uid: user_record(email_verified=False))

    middleware = auth_middleware.FirebaseAuthMiddleware(lambda scope, receive, send: None)
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/sessions"),
        headers={"Authorization": "Bearer token"},
        state=SimpleNamespace(),
    )

    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 403


def test_middleware_allows_google_user(monkeypatch):
    monkeypatch.setattr(auth_middleware, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_middleware.auth,
        "verify_id_token",
        lambda token: {"uid": "user-1", "firebase": {"sign_in_provider": "google.com"}},
    )
    monkeypatch.setattr(auth_middleware.auth, "get_user", lambda uid: user_record(email_verified=False, providers=["google.com"]))

    middleware = auth_middleware.FirebaseAuthMiddleware(lambda scope, receive, send: None)
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/sessions"),
        headers={"Authorization": "Bearer token"},
        state=SimpleNamespace(),
    )

    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    assert request.state.uid == "user-1"
