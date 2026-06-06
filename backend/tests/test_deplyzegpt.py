"""
Backend tests for DeplyzeGPT API
Tests: health, upload, file serving, image analysis (gemini + yolo26)
"""
import pytest
import requests
import os
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_IMAGE_PATH = "/tmp/test_image.jpg"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_BACKEND_TESTS") != "true" or not BASE_URL or not Path(TEST_IMAGE_PATH).exists(),
    reason="Live backend smoke tests require RUN_LIVE_BACKEND_TESTS=true, REACT_APP_BACKEND_URL, and /tmp/test_image.jpg.",
)


@pytest.fixture(scope="module")
def uploaded_file():
    """Upload a test image and return file info"""
    with open(TEST_IMAGE_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("test_image.jpg", f, "image/jpeg")}
        )
    assert resp.status_code == 200
    return resp.json()


# Health check
class TestHealth:
    def test_api_root(self):
        resp = requests.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        print(f"PASS: API root - {data}")


# Upload
class TestUpload:
    def test_upload_jpeg(self):
        with open(TEST_IMAGE_PATH, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/upload",
                files={"file": ("test_image.jpg", f, "image/jpeg")}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "file_id" in data
        assert "url" in data
        assert data["file_type"] == "image"
        assert data["size"] > 0
        print(f"PASS: Upload JPEG - file_id={data['file_id']}, size={data['size']}")

    def test_upload_invalid_type(self):
        resp = requests.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")}
        )
        assert resp.status_code == 400
        print(f"PASS: Upload invalid type - got 400 as expected")


# File serving
class TestFileServing:
    def test_serve_uploaded_file(self, uploaded_file):
        url = uploaded_file["url"]
        full_url = f"{BASE_URL}{url}"
        resp = requests.get(full_url)
        assert resp.status_code == 200
        assert len(resp.content) > 0
        print(f"PASS: File serving - {full_url}")

    def test_serve_nonexistent_file(self):
        resp = requests.get(f"{BASE_URL}/api/files/uploads/nonexistent.jpg")
        assert resp.status_code == 404
        print("PASS: 404 for nonexistent file")


# Image Analysis - Gemini
class TestAnalyzeGemini:
    def test_analyze_image_gemini(self, uploaded_file):
        resp = requests.post(
            f"{BASE_URL}/api/analyze/image",
            json={
                "file_url": uploaded_file["url"],
                "model": "gemini",
                "prompt": "Describe the shapes and colors in this image"
            },
            timeout=60
        )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("type") == "text"
        assert "content" in data
        assert len(data["content"]) > 0
        print(f"PASS: Gemini analysis - type={data['type']}, content_len={len(data['content'])}")
        if "suggestions" in data:
            print(f"  suggestions: {data['suggestions']}")


# Image Analysis - YOLO26
class TestAnalyzeYOLO:
    def test_analyze_image_yolo26(self, uploaded_file):
        resp = requests.post(
            f"{BASE_URL}/api/analyze/image",
            json={
                "file_url": uploaded_file["url"],
                "model": "yolo26",
                "confidence": 0.25
            },
            timeout=90  # YOLO model may need to download
        )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("type") == "image"
        assert "content" in data
        assert len(data["content"]) > 0  # base64 content
        print(f"PASS: YOLO26 analysis - type={data['type']}, detections={data.get('detections', [])}")
