import base64
import logging
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

import cv2

from locate_service import analyze_image_locate

logger = logging.getLogger(__name__)

DEFAULT_MAX_DURATION_SECONDS = 180
DEFAULT_MAX_FRAMES = 24
DEFAULT_SAMPLE_SECONDS = 5.0
DEFAULT_MIN_FRAMES = 6
DEFAULT_SCENE_THRESHOLD = 0.35
DEFAULT_MIN_GAP_SECONDS = 1.5
DEFAULT_FRAME_TIMEOUT_SECONDS = 180
DEFAULT_JOB_TIMEOUT_SECONDS = 1800
DEFAULT_OUTPUT_FPS = 24
MIN_FRAME_HOLD_SECONDS = 0.25

SHOWINFO_PTS_RE = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


class LocateVideoError(RuntimeError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class LocateVideoDurationError(LocateVideoError):
    pass


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def max_duration_seconds() -> int:
    return _env_int("LOCATE_VIDEO_MAX_DURATION_SECONDS", DEFAULT_MAX_DURATION_SECONDS)


def max_frames() -> int:
    return _env_int("LOCATE_VIDEO_MAX_FRAMES", DEFAULT_MAX_FRAMES)


def sample_seconds() -> float:
    return _env_float("LOCATE_VIDEO_SAMPLE_SECONDS", DEFAULT_SAMPLE_SECONDS, minimum=0.1)


def scene_threshold() -> float:
    return _env_float("LOCATE_VIDEO_SCENE_THRESHOLD", DEFAULT_SCENE_THRESHOLD, minimum=0.0)


def frame_timeout_seconds() -> int:
    return _env_int("LOCATE_VIDEO_FRAME_TIMEOUT_SECONDS", DEFAULT_FRAME_TIMEOUT_SECONDS, minimum=30)


def job_timeout_seconds() -> int:
    return _env_int("LOCATE_VIDEO_JOB_TIMEOUT_SECONDS", DEFAULT_JOB_TIMEOUT_SECONDS, minimum=120)


def output_fps() -> int:
    return _env_int("LOCATE_VIDEO_OUTPUT_FPS", DEFAULT_OUTPUT_FPS, minimum=1)


def _get_video_duration_seconds(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if frame_count <= 0 or fps <= 0:
            return 0.0
        return frame_count / fps
    finally:
        cap.release()


def validate_video_duration(duration_seconds: float, limit_seconds: Optional[int] = None) -> None:
    limit = limit_seconds or max_duration_seconds()
    if duration_seconds <= 0:
        raise LocateVideoDurationError("Could not read video duration for LocateAnything analysis.")
    if duration_seconds > limit:
        raise LocateVideoDurationError(
            f"LocateAnything video analysis supports videos up to {limit} seconds in v2.0."
        )


def _clamp_timestamp(timestamp: float, duration_seconds: float) -> float:
    end = max(0.0, duration_seconds - 0.001)
    return min(end, max(0.0, float(timestamp)))


def uniform_sample_timestamps(
    duration_seconds: float,
    sample_every_seconds: Optional[float] = None,
    min_frames: int = DEFAULT_MIN_FRAMES,
    frame_cap: Optional[int] = None,
) -> list[float]:
    sample_every = sample_every_seconds or sample_seconds()
    cap = frame_cap or max_frames()
    target = min(cap, max(min_frames, math.ceil(duration_seconds / sample_every)))
    if target <= 1:
        return [0.0]

    end = max(0.0, duration_seconds - 0.001)
    return [round((end * index) / (target - 1), 3) for index in range(target)]


def scene_change_timestamps(
    video_path: str,
    threshold: Optional[float] = None,
    timeout_seconds: int = 300,
) -> list[float]:
    threshold_value = scene_threshold() if threshold is None else threshold
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{threshold_value})',showinfo",
        "-vsync",
        "vfr",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Scene-change sampling failed: %s", exc)
        return []

    if result.returncode != 0:
        logger.warning("Scene-change sampling returned %s: %s", result.returncode, result.stderr[-300:])
        return []

    return [float(match.group(1)) for match in SHOWINFO_PTS_RE.finditer(result.stderr or "")]


def merge_sample_timestamps(
    uniform_timestamps: list[float],
    scene_timestamps: list[float],
    duration_seconds: float,
    min_gap_seconds: float = DEFAULT_MIN_GAP_SECONDS,
    frame_cap: Optional[int] = None,
) -> list[dict[str, Any]]:
    cap = frame_cap or max_frames()
    candidates: list[dict[str, Any]] = []
    for timestamp in uniform_timestamps:
        candidates.append({"timestamp_seconds": _clamp_timestamp(timestamp, duration_seconds), "sources": {"uniform"}})
    for timestamp in scene_timestamps:
        candidates.append({"timestamp_seconds": _clamp_timestamp(timestamp, duration_seconds), "sources": {"scene"}})

    candidates.sort(key=lambda item: item["timestamp_seconds"])

    merged: list[dict[str, Any]] = []
    for candidate in candidates:
        if merged and abs(candidate["timestamp_seconds"] - merged[-1]["timestamp_seconds"]) <= min_gap_seconds:
            merged[-1]["sources"].update(candidate["sources"])
            continue
        merged.append(candidate)

    if len(merged) > cap:
        merged = _thin_samples(merged, cap)

    samples = []
    for sample in merged:
        samples.append(
            {
                "timestamp_seconds": round(sample["timestamp_seconds"], 3),
                "source": "+".join(sorted(sample["sources"])),
            }
        )
    return samples


def _thin_samples(samples: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    if len(samples) <= cap:
        return samples
    if cap <= 1:
        return [samples[0]]

    last_index = len(samples) - 1
    selected = {0, last_index}
    for index in range(1, cap - 1):
        selected.add(round((index * last_index) / (cap - 1)))

    if len(selected) < cap:
        for index in range(last_index + 1):
            selected.add(index)
            if len(selected) == cap:
                break

    return [samples[index] for index in sorted(selected)[:cap]]


def build_frame_samples(video_path: str, duration_seconds: Optional[float] = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    duration = duration_seconds if duration_seconds is not None else _get_video_duration_seconds(video_path)
    validate_video_duration(duration)

    uniform = uniform_sample_timestamps(duration, sample_seconds(), DEFAULT_MIN_FRAMES, max_frames())
    scene = scene_change_timestamps(video_path, scene_threshold())
    samples = merge_sample_timestamps(uniform, scene, duration, DEFAULT_MIN_GAP_SECONDS, max_frames())
    if not samples:
        raise LocateVideoError("No video frames could be sampled for LocateAnything analysis.")

    sampling = {
        "strategy": "uniform_plus_scene_change",
        "duration_seconds": round(duration, 3),
        "sample_seconds": sample_seconds(),
        "scene_threshold": scene_threshold(),
        "min_gap_seconds": DEFAULT_MIN_GAP_SECONDS,
        "min_frames": DEFAULT_MIN_FRAMES,
        "max_frames": max_frames(),
        "uniform_count": len(uniform),
        "scene_count": len(scene),
        "selected_count": len(samples),
    }
    return samples, sampling


def _extract_frame_at_timestamp(video_path: str, timestamp_seconds: float, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        raise LocateVideoError(f"Could not extract video frame at {timestamp_seconds:.2f}s.")


def _decode_data_uri(data_uri: str) -> tuple[bytes, str]:
    if "," not in data_uri:
        raise LocateVideoError("LocateAnything returned an invalid frame image.")
    header, encoded = data_uri.split(",", 1)
    content_type = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        content_type = header[5:].split(";", 1)[0]
    return base64.b64decode(encoded), content_type


def _public_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in frame.items() if key not in {"path"}}


def _concat_file_path(path: str) -> str:
    # FFmpeg concat scripts use single-quoted paths; embedded quotes must be escaped.
    return Path(path).resolve().as_posix().replace("'", r"'\''")


def frame_display_durations(frames: list[dict[str, Any]], duration_seconds: float) -> list[float]:
    if not frames:
        return []
    if len(frames) == 1:
        return [max(MIN_FRAME_HOLD_SECONDS, duration_seconds)]

    timestamps = [float(frame["timestamp_seconds"]) for frame in frames]
    boundaries = [0.0]
    for previous, current in zip(timestamps, timestamps[1:]):
        boundaries.append(max(boundaries[-1], (previous + current) / 2.0))
    boundaries.append(max(boundaries[-1] + MIN_FRAME_HOLD_SECONDS, duration_seconds))

    durations = []
    for start, end in zip(boundaries, boundaries[1:]):
        durations.append(round(max(MIN_FRAME_HOLD_SECONDS, end - start), 3))
    return durations


def _stitch_annotated_frames(
    job_id: str,
    frames: list[dict[str, Any]],
    duration_seconds: float,
    outputs_dir: Path,
) -> str:
    if not frames:
        raise LocateVideoError("No annotated frames were produced for LocateAnything video output.")

    concat_path = outputs_dir / f"{job_id}_frames.ffconcat"
    final_path = outputs_dir / f"{job_id}.mp4"
    durations = frame_display_durations(frames, duration_seconds)

    lines = ["ffconcat version 1.0"]
    for frame, display_duration in zip(frames, durations):
        lines.append(f"file '{_concat_file_path(frame['path'])}'")
        lines.append(f"duration {display_duration:.3f}")
    lines.append(f"file '{_concat_file_path(frames[-1]['path'])}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vf",
        f"fps={output_fps()},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "23",
        "-preset",
        "fast",
        "-movflags",
        "+faststart",
        "-an",
        str(final_path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=max(300, int(duration_seconds * 10)),
    )
    if result.returncode != 0:
        raise LocateVideoError(f"FFmpeg video stitching failed: {result.stderr[-300:]}", status_code=500)
    if not final_path.exists() or final_path.stat().st_size <= 0:
        raise LocateVideoError("FFmpeg did not produce a LocateAnything MP4 output.", status_code=500)

    concat_path.unlink(missing_ok=True)
    return str(final_path)


def _update(progress_callback: Optional[Callable[[dict[str, Any]], None]], updates: dict[str, Any]) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(updates)
    except Exception as exc:
        logger.warning("Locate video progress update failed: %s", exc)


def process_video_locate(
    job_id: str,
    video_path: str,
    prompt: str,
    outputs_dir: Path,
    progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = outputs_dir / "_sampled"
    raw_dir.mkdir(parents=True, exist_ok=True)

    _update(progress_callback, {"status": "processing", "phase": "sampling", "progress": 3})
    samples, sampling = build_frame_samples(video_path)
    duration_seconds = float(sampling["duration_seconds"])
    total = len(samples)
    _update(
        progress_callback,
        {
            "status": "processing",
            "phase": "extracting",
            "progress": 5,
            "frame_total": total,
            "frame_completed": 0,
            "sampling": sampling,
        },
    )

    raw_frames: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        raw_path = raw_dir / f"source_{index:04d}.jpg"
        _extract_frame_at_timestamp(video_path, sample["timestamp_seconds"], raw_path)
        raw_frames.append({**sample, "index": index, "raw_path": raw_path})
        extract_progress = 5 + int((index / total) * 15)
        _update(progress_callback, {"phase": "extracting", "progress": min(extract_progress, 20)})

    frames: list[dict[str, Any]] = []
    _update(progress_callback, {"phase": "analyzing", "progress": 20, "frame_total": total, "frame_completed": 0})
    for frame in raw_frames:
        index = frame["index"]
        filename = f"frame_{index:04d}.jpg"
        output_path = outputs_dir / filename
        start = time.perf_counter()
        result = analyze_image_locate(
            str(frame["raw_path"]),
            prompt,
            timeout_seconds=frame_timeout_seconds(),
        )
        elapsed = round(time.perf_counter() - start, 3)
        image_bytes, _content_type = _decode_data_uri(result["content"])
        output_path.write_bytes(image_bytes)

        timings = dict(result.get("timings") or {})
        timings.setdefault("total_seconds", elapsed)
        timings["client_total_seconds"] = elapsed
        frame_entry = {
            "index": index,
            "filename": filename,
            "timestamp_seconds": frame["timestamp_seconds"],
            "source": frame["source"],
            "detections": result.get("detections", []),
            "raw_answer": result.get("raw_answer", ""),
            "generation_mode": result.get("generation_mode"),
            "model": result.get("model"),
            "timings": timings,
            "path": str(output_path),
        }
        frames.append(frame_entry)
        analysis_progress = 20 + int((index / total) * 68)
        _update(
            progress_callback,
            {
                "phase": "analyzing",
                "progress": min(analysis_progress, 88),
                "frame_total": total,
                "frame_completed": index,
            },
        )

    _update(progress_callback, {"phase": "stitching", "progress": 92})
    output_path = _stitch_annotated_frames(job_id, frames, duration_seconds, outputs_dir)

    _update(progress_callback, {"phase": "uploading", "progress": 95})
    return {
        "type": "video",
        "frames": [_public_frame(frame) for frame in frames],
        "output_path": output_path,
        "sampling": sampling,
    }
