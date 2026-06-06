# LocateAnything Video Integration Plan

## Summary

LocateAnything video analysis ships as sampled-frame grounding, not full-frame video rendering. The YOLO video path still produces an annotated MP4 through `backend/video_processor.py`; LocateAnything uses `backend/locate_video_processor.py` because a 3B VLM cannot run economically on every video frame.

The v2.0 workflow keeps the existing async job shape: upload to R2, create a Firestore job, queue a FastAPI background task, update `jobs/{uid}/items/{job_id}`, and let the frontend listen for progress. The completed artifact is a frame gallery plus `manifest.json` packaged as `output.zip`.

## Frame Sampling Strategy

- Videos over `LOCATE_VIDEO_MAX_DURATION_SECONDS=180` are rejected for v2.0.
- Uniform sampling targets one frame every `LOCATE_VIDEO_SAMPLE_SECONDS=5`, with at least 6 frames for short clips and a hard cap of `LOCATE_VIDEO_MAX_FRAMES=24`.
- Scene-change candidates are detected with FFmpeg `select='gt(scene,0.35)'`, merged with uniform timestamps, de-duped within 1.5 seconds, and capped while preserving the first and last selected samples.
- LocateAnything frame extraction uses FFmpeg timestamp extraction. Scene detection uses FFmpeg's scene filter; `-skip_frame nokey` is not used because keyframes are encoder artifacts, not semantic scene changes.

This gives useful temporal coverage without letting a one-minute 30 FPS clip turn into 1,800 sequential GPU calls.

## Backend Integration

- `POST /api/analyze/video` allows `locate-anything` only when `ENABLE_LOCATE_ANYTHING_VIDEO=true`.
- `backend/locate_video_processor.py` extracts sampled JPEGs, calls the existing Locate image client sequentially, records per-frame timings, writes annotated frames, writes `manifest.json`, and packages `output.zip`.
- The existing GPU worker remains single-image and sequential for v2.0. No `/predict_batch` endpoint is required yet.
- Recommended Cloud Run GPU settings remain: L4, concurrency `1`, max instances `1`, timeout `600s`, instance-based billing, 4 vCPU/16 GiB minimum, 8 vCPU/32 GiB preferred.
- Runtime controls:
  - `LOCATE_VIDEO_FRAME_TIMEOUT_SECONDS=180`
  - `LOCATE_VIDEO_JOB_TIMEOUT_SECONDS=1800`
  - `LOCATE_VIDEO_MAX_FRAMES=24`
  - `LOCATE_VIDEO_SAMPLE_SECONDS=5`
  - `LOCATE_VIDEO_SCENE_THRESHOLD=0.35`

## Output And Firestore Contract

R2 output layout:

```text
outputs/{uid}/{session_id}/{job_id}/frame_0001.jpg
outputs/{uid}/{session_id}/{job_id}/frame_0002.jpg
outputs/{uid}/{session_id}/{job_id}/manifest.json
outputs/{uid}/{session_id}/{job_id}/output.zip
```

Job documents can include optional fields: `phase`, `frame_total`, `frame_completed`, `sampling`, `frames`, `manifest_key`, and `output_key`. Firestore stores R2 keys only. API responses add fresh presigned frame URLs through `GET /api/analyze/video/status/{job_id}` and session restore.

Assistant messages use `output_type: "frame_gallery"` with `frames` metadata and `output_r2_path` pointing to `output.zip`.

## Frontend Behavior

- `REACT_APP_ENABLE_LOCATE_ANYTHING_VIDEO=true` allows the Locate model for video attachments.
- Progress shows phases: queued, extracting sampled frames, analyzing frame `n/N`, packaging, and uploading.
- Completed results render as a timestamped annotated-frame gallery.
- The download button fetches the authenticated API ZIP download URL; the browser never fetches raw R2 URLs directly.

## Timing And Cost

Public LocateAnything throughput is reported as 12.7 boxes/sec on a single H100 with batch size 1, not L4 frame/sec. v2.0 records actual `timings.total_seconds` per frame in the manifest before making stronger latency promises.

Planning estimate on L4 is 4-10 seconds per sampled frame when warm. At roughly 12 sampled frames per minute of video, expected processing is 48-120 seconds per video minute, plus 60-180 seconds cold start if min instances is 0.

At current Cloud Run GPU pricing, L4 without zonal redundancy plus 4 vCPU/16 GiB is about `$0.0174/min` active. Warm compute cost is roughly `$0.014-$0.035` per video minute with this sampling plan, excluding storage and egress.

## Phasing

v2.0 ships feature-flagged sampled-frame galleries, 180-second duration limit, 24-frame cap, sequential worker calls, ZIP download, Firestore progress, and session restore.

v2.1 defers `/predict_batch`, batch-size 2/4 benchmarks, Cloud Tasks or Cloud Run Jobs, longer videos, query-aware keyframe ranking, optional stitched low-FPS MP4s, and tracking/interpolation between sampled frames.

## Sources

- NVIDIA LocateAnything research page: https://research.nvidia.com/labs/lpr/locate-anything/
- Hugging Face LocateAnything-3B model card: https://huggingface.co/nvidia/LocateAnything-3B
- FFmpeg filters: https://ffmpeg.org/ffmpeg-filters.html
- FFmpeg codec skip_frame docs: https://ffmpeg.org/ffmpeg-codecs.html
- Cloud Run GPU docs: https://docs.cloud.google.com/run/docs/configuring/services/gpu
- Cloud Run GPU best practices: https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices
- Cloud Run concurrency: https://docs.cloud.google.com/run/docs/about-concurrency
- Cloud Run timeout: https://docs.cloud.google.com/run/docs/configuring/request-timeout
- Cloud Run pricing: https://cloud.google.com/run/pricing
- Frame Sampling Strategies Matter: https://arxiv.org/abs/2509.14769
- Adaptive Keyframe Sampling for Long Video Understanding: https://openaccess.thecvf.com/content/CVPR2025/papers/Tang_Adaptive_Keyframe_Sampling_for_Long_Video_Understanding_CVPR_2025_paper.pdf
- Transformers pipelines batching: https://huggingface.co/docs/transformers/en/main_classes/pipelines
- Transformers continuous batching: https://huggingface.co/docs/transformers/main//continuous_batching
