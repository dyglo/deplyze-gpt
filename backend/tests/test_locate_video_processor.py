import base64
import json
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locate_video_processor


def _jpeg_data_uri(color=(0, 0, 0)) -> str:
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    image[:] = color
    ok, buf = cv2.imencode(".jpg", image)
    assert ok
    return f"data:image/jpeg;base64,{base64.b64encode(buf.tobytes()).decode('utf-8')}"


def test_uniform_sampling_uses_minimum_and_frame_cap():
    timestamps = locate_video_processor.uniform_sample_timestamps(
        duration_seconds=12,
        sample_every_seconds=5,
        min_frames=6,
        frame_cap=4,
    )

    assert len(timestamps) == 4
    assert timestamps[0] == 0
    assert timestamps[-1] == pytest.approx(11.999)


def test_merge_sampling_dedupes_scene_candidates_and_preserves_bounds():
    samples = locate_video_processor.merge_sample_timestamps(
        uniform_timestamps=[0, 5, 10, 15, 20],
        scene_timestamps=[5.4, 14.9, 19.8],
        duration_seconds=21,
        min_gap_seconds=1.5,
        frame_cap=4,
    )

    assert len(samples) == 4
    assert samples[0]["timestamp_seconds"] == 0
    assert samples[-1]["timestamp_seconds"] == pytest.approx(19.8)
    assert any(sample["source"] == "scene+uniform" for sample in samples)


def test_validate_video_duration_rejects_long_video():
    with pytest.raises(locate_video_processor.LocateVideoDurationError):
        locate_video_processor.validate_video_duration(181, limit_seconds=180)


def test_process_video_locate_writes_manifest_and_zip(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCATE_VIDEO_MAX_FRAMES", "3")
    monkeypatch.setenv("LOCATE_VIDEO_FRAME_TIMEOUT_SECONDS", "180")

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"fake video")

    def fake_extract(_video_path, _timestamp, output_path):
        image = np.zeros((24, 32, 3), dtype=np.uint8)
        cv2.imwrite(str(output_path), image)

    calls = []

    def fake_analyze(file_path, prompt, timeout_seconds=None, **_kwargs):
        calls.append((file_path, prompt, timeout_seconds))
        return {
            "type": "image",
            "content": _jpeg_data_uri((0, 255, 0)),
            "detections": [{"kind": "box", "class": "person", "bbox": [1, 2, 20, 22]}],
            "raw_answer": "<box><1><2><20><22></box>",
            "generation_mode": "hybrid",
            "timings": {"total_seconds": 1.23},
            "model": "nvidia/LocateAnything-3B",
        }

    monkeypatch.setattr(locate_video_processor, "_get_video_duration_seconds", lambda _path: 12)
    monkeypatch.setattr(locate_video_processor, "scene_change_timestamps", lambda *_args, **_kwargs: [4.9, 8.1])
    monkeypatch.setattr(locate_video_processor, "_extract_frame_at_timestamp", fake_extract)
    monkeypatch.setattr(locate_video_processor, "analyze_image_locate", fake_analyze)

    progress = []
    result = locate_video_processor.process_video_locate(
        "job-123",
        str(video_path),
        "locate people",
        tmp_path / "outputs",
        progress.append,
    )

    assert result["type"] == "frame_gallery"
    assert len(result["frames"]) == 3
    assert len(calls) == 3
    assert all(call[1] == "locate people" for call in calls)
    assert all(call[2] == 180 for call in calls)

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["type"] == "frame_gallery"
    assert manifest["sampling"]["selected_count"] == 3
    assert "path" not in manifest["frames"][0]
    assert manifest["frames"][0]["timings"]["total_seconds"] == 1.23

    with zipfile.ZipFile(result["zip_path"]) as archive:
        assert "manifest.json" in archive.namelist()
        assert "frame_0001.jpg" in archive.namelist()

    assert progress[-1]["phase"] == "uploading"
