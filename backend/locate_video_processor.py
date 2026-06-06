import json
import logging
import math
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import cv2

from locate_service import analyze_image_locate, render_locate_annotations

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

SHOWINFO_PTS_RE = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float
    fps: float
    width: int
    height: int
    frame_count: int


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


def _parse_frame_rate(value: Any) -> float:
    if not value:
        return 0.0
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return 0.0
            return float(numerator) / denominator_value
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _bounded_fps(value: float) -> float:
    if value <= 0 or math.isnan(value) or math.isinf(value):
        return float(DEFAULT_OUTPUT_FPS)
    return min(60.0, max(1.0, float(value)))


def output_fps(source_fps: Optional[float] = None) -> float:
    configured = os.environ.get("LOCATE_VIDEO_OUTPUT_FPS")
    if configured:
        try:
            return _bounded_fps(float(configured))
        except ValueError:
            pass
    if source_fps:
        return _bounded_fps(float(source_fps))
    return float(DEFAULT_OUTPUT_FPS)


def _opencv_video_metadata(video_path: str) -> VideoMetadata:
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return VideoMetadata(0.0, 0.0, 0, 0, 0)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if frame_count > 0 and fps > 0 else 0.0
        return VideoMetadata(float(duration), float(fps), width, height, int(frame_count))
    finally:
        cap.release()


def get_video_metadata(video_path: str) -> VideoMetadata:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("FFprobe metadata read failed, falling back to OpenCV: %s", exc)
        return _opencv_video_metadata(video_path)

    if result.returncode != 0:
        logger.warning("FFprobe metadata read returned %s: %s", result.returncode, result.stderr[-300:])
        return _opencv_video_metadata(video_path)

    try:
        data = json.loads(result.stdout or "{}")
    except ValueError:
        return _opencv_video_metadata(video_path)

    stream = (data.get("streams") or [{}])[0] if isinstance(data.get("streams"), list) else {}
    format_info = data.get("format") or {}

    def _float_field(source: dict, key: str) -> float:
        try:
            return float(source.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    duration = _float_field(format_info, "duration") or _float_field(stream, "duration")
    fps = _parse_frame_rate(stream.get("avg_frame_rate")) or _parse_frame_rate(stream.get("r_frame_rate"))
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    try:
        frame_count = int(stream.get("nb_frames") or 0)
    except (TypeError, ValueError):
        frame_count = 0

    fallback = _opencv_video_metadata(video_path)
    duration = duration or fallback.duration_seconds
    fps = fps or fallback.fps
    width = width or fallback.width
    height = height or fallback.height
    frame_count = frame_count or fallback.frame_count
    return VideoMetadata(float(duration), float(fps), width, height, frame_count)


def _get_video_duration_seconds(video_path: str) -> float:
    return get_video_metadata(video_path).duration_seconds


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


def _public_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in frame.items() if key not in {"path"}}


def _frame_timestamp_seconds(cap: cv2.VideoCapture, frame_index: int, fps: float) -> float:
    pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0
    if pos_ms > 0:
        return float(pos_ms) / 1000.0
    return float(frame_index) / max(fps, 1.0)


def _write_jpeg(path: Path, frame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise LocateVideoError(f"Could not write sampled video frame {path.name}.", status_code=500)


def extract_sample_frames(
    video_path: str,
    samples: list[dict[str, Any]],
    raw_dir: Path,
    metadata: Optional[VideoMetadata] = None,
) -> list[dict[str, Any]]:
    if not samples:
        return []

    raw_dir.mkdir(parents=True, exist_ok=True)
    video_metadata = metadata or get_video_metadata(video_path)
    fps = output_fps(video_metadata.fps)
    half_frame_seconds = 0.5 / max(fps, 1.0)
    sorted_samples = sorted(samples, key=lambda sample: float(sample["timestamp_seconds"]))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise LocateVideoError(f"Cannot open video file for LocateAnything sampling: {video_path}", status_code=422)

    raw_frames: list[dict[str, Any]] = []
    next_sample_index = 0
    frame_index = 0
    last_frame = None
    last_timestamp = 0.0

    try:
        while next_sample_index < len(sorted_samples):
            ret, frame = cap.read()
            if not ret:
                break

            last_frame = frame
            last_timestamp = _frame_timestamp_seconds(cap, frame_index, fps)
            while (
                next_sample_index < len(sorted_samples)
                and float(sorted_samples[next_sample_index]["timestamp_seconds"]) <= last_timestamp + half_frame_seconds
            ):
                sample = sorted_samples[next_sample_index]
                index = next_sample_index + 1
                raw_path = raw_dir / f"source_{index:04d}.jpg"
                _write_jpeg(raw_path, frame)
                raw_frames.append(
                    {
                        **sample,
                        "index": index,
                        "raw_path": raw_path,
                        "extracted_timestamp_seconds": round(last_timestamp, 3),
                    }
                )
                next_sample_index += 1

            frame_index += 1
    finally:
        cap.release()

    if last_frame is None:
        raise LocateVideoError("Could not read any frames from the uploaded video.", status_code=422)

    while next_sample_index < len(sorted_samples):
        sample = sorted_samples[next_sample_index]
        index = next_sample_index + 1
        raw_path = raw_dir / f"source_{index:04d}.jpg"
        _write_jpeg(raw_path, last_frame)
        raw_frames.append(
            {
                **sample,
                "index": index,
                "raw_path": raw_path,
                "extracted_timestamp_seconds": round(last_timestamp, 3),
                "extraction_fallback": "last_decoded_frame",
            }
        )
        next_sample_index += 1

    return raw_frames


def _even_output_size(width: int, height: int) -> tuple[int, int]:
    return max(2, width - (width % 2)), max(2, height - (height % 2))


def detection_intervals(frames: list[dict[str, Any]], duration_seconds: float) -> list[dict[str, Any]]:
    if not frames:
        return []

    ordered = sorted(frames, key=lambda frame: float(frame["timestamp_seconds"]))
    boundaries = [0.0]
    for previous, current in zip(ordered, ordered[1:]):
        midpoint = (float(previous["timestamp_seconds"]) + float(current["timestamp_seconds"])) / 2.0
        boundaries.append(max(boundaries[-1], midpoint))
    boundaries.append(max(duration_seconds, boundaries[-1]))

    intervals = []
    for index, frame in enumerate(ordered):
        intervals.append(
            {
                "start": boundaries[index],
                "end": boundaries[index + 1],
                "frame": frame,
            }
        )
    return intervals


def _detections_for_timestamp(intervals: list[dict[str, Any]], timestamp_seconds: float) -> list[dict]:
    if not intervals:
        return []

    for interval in intervals:
        if timestamp_seconds < interval["end"]:
            return interval["frame"].get("detections", [])
    return intervals[-1]["frame"].get("detections", [])


def _render_full_duration_video(
    job_id: str,
    video_path: str,
    frames: list[dict[str, Any]],
    metadata: VideoMetadata,
    duration_seconds: float,
    outputs_dir: Path,
    progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> str:
    if not frames:
        raise LocateVideoError("No LocateAnything frame detections were produced for video output.")

    temp_path = outputs_dir / f"{job_id}_raw.avi"
    final_path = outputs_dir / f"{job_id}.mp4"
    fps = output_fps(metadata.fps)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise LocateVideoError(f"Cannot open video file for LocateAnything rendering: {video_path}", status_code=422)

    width = metadata.width or int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = metadata.height or int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        raise LocateVideoError("Could not read video dimensions for LocateAnything rendering.", status_code=422)

    out_width, out_height = _even_output_size(width, height)
    out = cv2.VideoWriter(
        str(temp_path),
        cv2.VideoWriter_fourcc(*"XVID"),
        fps,
        (out_width, out_height),
    )
    if not out.isOpened():
        cap.release()
        raise LocateVideoError("Failed to initialize LocateAnything video writer.", status_code=500)

    intervals = detection_intervals(frames, duration_seconds)
    total_frames = metadata.frame_count or int(max(duration_seconds, 1.0) * fps)
    progress_step = max(1, total_frames // 20)
    frame_index = 0

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_seconds = _frame_timestamp_seconds(cap, frame_index, fps)
            detections = _detections_for_timestamp(intervals, timestamp_seconds)
            annotated = render_locate_annotations(frame, detections)
            if (annotated.shape[1], annotated.shape[0]) != (out_width, out_height):
                annotated = cv2.resize(annotated, (out_width, out_height), interpolation=cv2.INTER_AREA)

            out.write(annotated)
            frame_index += 1

            if frame_index % progress_step == 0:
                raw_progress = 89 + int((frame_index / max(total_frames, 1)) * 5)
                _update(progress_callback, {"phase": "stitching", "progress": min(raw_progress, 94)})
    finally:
        cap.release()
        out.release()

    if frame_index <= 0 or not temp_path.exists() or temp_path.stat().st_size <= 0:
        temp_path.unlink(missing_ok=True)
        raise LocateVideoError("LocateAnything did not produce any annotated video frames.", status_code=500)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(temp_path),
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

    temp_path.unlink(missing_ok=True)
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
    metadata = get_video_metadata(video_path)
    samples, sampling = build_frame_samples(video_path, metadata.duration_seconds)
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

    raw_frames = extract_sample_frames(video_path, samples, raw_dir, metadata)
    _update(progress_callback, {"phase": "extracting", "progress": 20})

    frames: list[dict[str, Any]] = []
    _update(progress_callback, {"phase": "analyzing", "progress": 20, "frame_total": total, "frame_completed": 0})
    for frame in raw_frames:
        index = frame["index"]
        filename = f"source_{index:04d}.jpg"
        start = time.perf_counter()
        result = analyze_image_locate(
            str(frame["raw_path"]),
            prompt,
            timeout_seconds=frame_timeout_seconds(),
        )
        elapsed = round(time.perf_counter() - start, 3)

        timings = dict(result.get("timings") or {})
        timings.setdefault("total_seconds", elapsed)
        timings["client_total_seconds"] = elapsed
        frame_entry = {
            "index": index,
            "filename": filename,
            "timestamp_seconds": frame["timestamp_seconds"],
            "extracted_timestamp_seconds": frame.get("extracted_timestamp_seconds"),
            "extraction_fallback": frame.get("extraction_fallback"),
            "source": frame["source"],
            "detections": result.get("detections", []),
            "raw_answer": result.get("raw_answer", ""),
            "generation_mode": result.get("generation_mode"),
            "model": result.get("model"),
            "timings": timings,
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

    _update(progress_callback, {"phase": "stitching", "progress": 89})
    output_path = _render_full_duration_video(job_id, video_path, frames, metadata, duration_seconds, outputs_dir, progress_callback)

    _update(progress_callback, {"phase": "uploading", "progress": 95})
    return {
        "type": "video",
        "frames": [_public_frame(frame) for frame in frames],
        "output_path": output_path,
        "sampling": sampling,
    }
