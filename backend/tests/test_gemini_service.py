import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.api_core import exceptions as google_exceptions

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gemini_service


def test_generate_with_retry_succeeds_after_quota_error(monkeypatch):
    calls = {"count": 0}
    sleeps = []

    def operation():
        calls["count"] += 1
        if calls["count"] == 1:
            raise google_exceptions.ResourceExhausted("quota exceeded")
        return "ok"

    monkeypatch.setattr(gemini_service.time, "sleep", lambda delay: sleeps.append(delay))

    assert gemini_service._generate_with_retry(operation) == "ok"
    assert calls["count"] == 2
    assert sleeps == [2]


def test_generate_with_retry_exhausts_quota_errors(monkeypatch):
    sleeps = []

    def operation():
        raise google_exceptions.ResourceExhausted("quota exceeded")

    monkeypatch.setattr(gemini_service.time, "sleep", lambda delay: sleeps.append(delay))

    with pytest.raises(gemini_service.GeminiServiceError) as error:
        gemini_service._generate_with_retry(operation)

    assert str(error.value) == gemini_service.HIGH_DEMAND_MESSAGE
    assert sleeps == [2, 4, 8]


def test_generate_with_retry_sanitizes_non_quota_errors(capsys):
    def operation():
        raise RuntimeError("provider secret stack trace")

    with pytest.raises(gemini_service.GeminiServiceError) as error:
        gemini_service._generate_with_retry(operation)

    assert str(error.value) == gemini_service.GENERIC_GEMINI_MESSAGE
    assert "provider secret" not in str(error.value)

    structured_log = json.loads(capsys.readouterr().err.strip())
    assert structured_log["event"] == "vertex_gemini_error"
    assert structured_log["operation"] == "generate_content"
    assert structured_log["model"] == gemini_service.GEMINI_MODEL
    assert structured_log["exception_type"] == "RuntimeError"


def test_permission_errors_do_not_surface_vertex_configuration():
    error = google_exceptions.Forbidden("Permission 'aiplatform.endpoints.predict' denied")

    assert gemini_service.clean_gemini_error(error) == "Gemini is not available right now. Please try again later."


def test_analyze_image_uses_vertex_model(monkeypatch, tmp_path):
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"fake image bytes")
    captured = {}

    class FakeImage:
        @staticmethod
        def load_from_file(location):
            captured["image_location"] = location
            return {"location": location}

    class FakePart:
        @staticmethod
        def from_text(text):
            return {"text": text}

        @staticmethod
        def from_image(image):
            return {"image": image}

    class FakeModel:
        def generate_content(self, contents, generation_config):
            captured["contents"] = contents
            captured["generation_config"] = generation_config
            return SimpleNamespace(text="Analysis complete.\n\nSuggestions:\n1. Export report\n2. Run detection\n3. Save session")

    monkeypatch.setattr(gemini_service, "Image", FakeImage)
    monkeypatch.setattr(gemini_service, "Part", FakePart)
    monkeypatch.setattr(gemini_service, "_get_model", lambda system_prompt: FakeModel())
    monkeypatch.setattr(gemini_service, "_generate_config", lambda: {"max_output_tokens": 2048})

    result = gemini_service._analyze_image_sync(str(image_path), "Describe this image", "system")

    assert captured["image_location"] == str(image_path)
    assert captured["contents"][0] == {"text": "Describe this image"}
    assert result["type"] == "text"
    assert result["suggestions"] == ["Export report", "Run detection", "Save session"]
