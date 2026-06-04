# YOLO Natural Language Class Filtering Phase

## Summary

This phase adds natural language class filtering for YOLO26 image and video analysis across:

- `yolo26` object detection.
- `yolo26-seg` instance segmentation.
- `yolo26-sem` semantic segmentation.

Users can now type prompts such as `detect only cars, trucks or van`, `segment only the dog`, or `Perform semantic segmentation on person`. The backend maps requested class names to the active model's class IDs and passes them to Ultralytics `predict(..., classes=[...])`. When a requested class is unsupported by the active model, the app returns a short inline error with examples instead of showing a long class dump or running an empty inference job.

## Behavior

- Class filtering is deterministic and vocabulary-based; it does not call an LLM.
- The active YOLO model's `model.names` dictionary is the source of truth.
- Detection and instance segmentation use COCO class IDs.
- Semantic segmentation uses the Cityscapes class IDs exposed by the bundled YOLO semantic model.
- `van` and `vans` are treated as practical aliases for COCO `truck`.
- Generic prompts such as `detect all objects`, `describe this image in detail`, and `full scene` keep the existing unfiltered inference behavior.
- Invalid class requests fail before inference starts and create an assistant error message in the chat history.

## Video Quality Improvements

The video pipeline was updated so filtered videos do not flicker or lose moving objects between frames:

- Detection and instance segmentation now run inference on every video frame instead of sampling and reusing stale results.
- Detection and instance segmentation video inference uses `imgsz=960`.
- Filtered video prompts use `conf=0.18` to reduce missed objects.
- Instance segmentation uses `retina_masks=True` for sharper masks.
- Multi-class filtered prompts use `agnostic_nms=True` to reduce duplicate overlays when similar classes overlap, such as `car` and `truck`.
- Semantic video inference was raised to `imgsz=768` and semantic output scaling was raised to a `1280` pixel max side.

## Validation

Local checks completed:

```powershell
python -B -m py_compile backend\server.py backend\yolo_service.py backend\video_processor.py
python -m pytest backend\tests\test_yolo_class_filter.py -q
```

The focused backend test suite passed with `7 passed`.

Manual video checks completed with `video/video-test.mp4`:

- `yolo26-seg` with `detect only cars, trucks or van` produced a processed video where the main moving vehicles stay segmented across sampled frames.
- `yolo26-sem` with `Perform semantic segmentation on person` produced a processed semantic video and no class-filter error.

The full legacy backend smoke suite still requires a configured `REACT_APP_BACKEND_URL` and `/tmp/test_image.jpg`; without those environment inputs it fails before exercising this feature.

## Files Changed

- `backend/yolo_service.py`: prompt parsing, class aliasing, class-filter errors, image inference filtering, semantic render/report filtering.
- `backend/server.py`: image/video request orchestration, pre-inference validation, failed-job/error-message handling.
- `backend/video_processor.py`: filtered video quality settings and per-frame inference.
- `backend/tests/test_yolo_class_filter.py`: parser, error, predict-kwargs, and semantic filtering coverage.
- `video/video-test.mp4`: local video fixture used for manual validation.

## Follow-Up Ideas

- Add integration tests with mocked Firebase/R2 storage for `/api/analyze/image` and `/api/analyze/video`.
- Add a queue-backed video worker for production-scale long-running jobs.
- Add a lightweight UI affordance that shows the resolved class filter before processing starts.
