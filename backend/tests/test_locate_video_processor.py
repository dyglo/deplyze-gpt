import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locate_video_processor


def _write_test_video(path: Path, frame_count: int = 12, fps: float = 6.0, size=(32, 24)) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened()
    for index in range(frame_count):
        image = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        image[:, :] = (index * 13 % 255, 80, 160)
        writer.write(image)
    writer.release()


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


def test_extract_sample_frames_falls_back_to_last_decoded_frame_for_tail_metadata(tmp_path):
    video_path = tmp_path / "input.mp4"
    _write_test_video(video_path, frame_count=10, fps=10.0)
    metadata = locate_video_processor.VideoMetadata(
        duration_seconds=2.0,
        fps=10.0,
        width=32,
        height=24,
        frame_count=20,
    )
    samples = [
        {"timestamp_seconds": 0.0, "source": "uniform"},
        {"timestamp_seconds": 0.5, "source": "uniform"},
        {"timestamp_seconds": 1.8, "source": "uniform"},
    ]

    frames = locate_video_processor.extract_sample_frames(video_path, samples, tmp_path / "raw", metadata)

    assert len(frames) == 3
    assert all(frame["raw_path"].exists() for frame in frames)
    assert frames[-1]["extraction_fallback"] == "last_decoded_frame"


def test_render_full_duration_video_reuses_nearest_sample_detections(monkeypatch, tmp_path):
    video_path = tmp_path / "input.mp4"
    _write_test_video(video_path, frame_count=3, fps=3.0)
    metadata = locate_video_processor.VideoMetadata(
        duration_seconds=1.0,
        fps=3.0,
        width=32,
        height=24,
        frame_count=3,
    )
    sample_detections = [{"kind": "box", "class": "target", "bbox": [4, 4, 20, 18]}]
    analyzed_frames = [
        {
            "index": 1,
            "timestamp_seconds": 0.0,
            "detections": sample_detections,
            "width": 32,
            "height": 24,
        }
    ]

    rendered_detections = []

    def fake_render(image, detections):
        rendered_detections.append(list(detections))
        return image.copy()

    monkeypatch.setattr(locate_video_processor, "render_locate_annotations", fake_render)

    output_path = locate_video_processor._render_full_duration_video(
        "job-123",
        str(video_path),
        metadata,
        1.0,
        tmp_path,
        analyzed_frames,
    )
    cap = cv2.VideoCapture(output_path)
    try:
        assert cap.isOpened()
        assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == pytest.approx(3, abs=1)
        assert cap.get(cv2.CAP_PROP_FPS) == pytest.approx(3.0, abs=0.2)
    finally:
        cap.release()

    assert rendered_detections == [sample_detections, sample_detections, sample_detections]


def test_merge_sampling_can_reject_over_frame_cap():
    with pytest.raises(locate_video_processor.LocateVideoFrameCapError) as exc:
        locate_video_processor.merge_sample_timestamps(
            uniform_timestamps=[0, 5, 10],
            scene_timestamps=[1, 2, 3, 4, 6, 7],
            duration_seconds=12,
            min_gap_seconds=0.1,
            frame_cap=4,
            reject_over_cap=True,
        )

    assert "current limit is 4 analysis frames" in str(exc.value)


def test_process_video_locate_writes_mp4_output(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCATE_VIDEO_MAX_FRAMES", "3")
    monkeypatch.setenv("LOCATE_VIDEO_FRAME_TIMEOUT_SECONDS", "180")

    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"fake video")

    def fake_render(_job_id, _video_path, _metadata, _duration_seconds, outputs_dir, frames, _progress_callback=None):
        assert frames[0]["detections"][0]["class"] == "person"
        output_path = outputs_dir / "job-123.mp4"
        output_path.write_bytes(b"fake mp4")
        return str(output_path)

    def fake_analyze(_raw_frames, prompt, _progress_callback=None):
        assert prompt == "locate people"
        frames = [
            {
                "index": 1,
                "filename": "frame_000001.jpg",
                "timestamp_seconds": 0.0,
                "source": "uniform",
                "detections": [{"kind": "box", "class": "person", "bbox": [1, 2, 20, 22]}],
                "raw_answer": "<box><1><2><20><22></box>",
                "generation_mode": "hybrid",
                "timings": {"total_seconds": 1.23},
                "model": "nvidia/LocateAnything-3B",
            }
        ]
        return frames, {"backend": "test-batch", "batch_size": 3, "batch_total": 1}

    monkeypatch.setattr(
        locate_video_processor,
        "get_video_metadata",
        lambda _path: locate_video_processor.VideoMetadata(12.0, 6.0, 32, 24, 72),
    )
    monkeypatch.setattr(
        locate_video_processor,
        "build_frame_samples",
        lambda _path, _duration=None, enforce_frame_cap=True: (
            [{"timestamp_seconds": 0.0, "source": "uniform"}],
            {"strategy": "test", "selected_count": 1},
        ),
    )
    monkeypatch.setattr(
        locate_video_processor,
        "extract_sample_frames",
        lambda _path, _samples, _raw_dir, _metadata=None: [
            {"index": 1, "raw_path": tmp_path / "source_0001.jpg", "timestamp_seconds": 0.0, "source": "uniform"}
        ],
    )
    monkeypatch.setattr(locate_video_processor, "_analyze_sample_frames", fake_analyze)
    monkeypatch.setattr(locate_video_processor, "_render_full_duration_video", fake_render)

    progress = []
    result = locate_video_processor.process_video_locate(
        "job-123",
        str(video_path),
        "locate people",
        tmp_path / "outputs",
        progress.append,
    )

    assert result["type"] == "video"
    assert len(result["frames"]) == 1
    assert result["output_path"].endswith(".mp4")
    assert Path(result["output_path"]).read_bytes() == b"fake mp4"

    assert result["frames"][0]["timings"]["total_seconds"] == 1.23
    assert "path" not in result["frames"][0]
    assert result["backend"] == "test-batch"
    assert result["batch_size"] == 3
    assert progress[-1]["phase"] == "uploading"
