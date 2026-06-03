import cv2
import subprocess
import logging
import os
from pathlib import Path
from pymongo import MongoClient

logger = logging.getLogger(__name__)


def process_video_yolo(
    job_id: str,
    video_path: str,
    model_type: str,
    confidence: float,
    outputs_dir: Path,
) -> str:
    """
    Process a video file with a YOLO model.
    Annotates each frame, writes with OpenCV, then re-encodes with FFmpeg (H.264, yuv420p).
    Updates job progress in MongoDB synchronously.
    Returns the final output path.
    """
    from yolo_service import get_model

    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    sync_client = MongoClient(mongo_url)
    sync_db = sync_client[db_name]

    def update_progress(progress: int, status: str = "processing"):
        try:
            sync_db.video_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"progress": progress, "status": status}},
            )
        except Exception as e:
            logger.warning(f"Progress update failed: {e}")

    temp_path = str(outputs_dir / f"{job_id}_raw.avi")
    final_path = str(outputs_dir / f"{job_id}.mp4")

    try:
        model = get_model(model_type)
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 500

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(temp_path, fourcc, fps, (width, height))

        if not out.isOpened():
            raise ValueError("Failed to initialize VideoWriter")

        update_progress(5)
        frame_num = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            results = model.predict(frame, conf=confidence, verbose=False)
            annotated = results[0].plot()
            out.write(annotated)
            frame_num += 1

            if frame_num % 10 == 0:
                raw_progress = 5 + int((frame_num / total_frames) * 75)
                update_progress(min(raw_progress, 80))

        cap.release()
        out.release()

        update_progress(83)

        # Re-encode with FFmpeg: H.264 libx264, yuv420p, crf 23
        cmd = [
            'ffmpeg', '-y',
            '-i', temp_path,
            '-vcodec', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            '-preset', 'fast',
            '-movflags', '+faststart',
            final_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise ValueError(f"FFmpeg failed: {result.stderr[-300:]}")

        Path(temp_path).unlink(missing_ok=True)
        update_progress(100, "done")

        return final_path

    except Exception as e:
        logger.error(f"Video processing error for job {job_id}: {e}")
        try:
            sync_db.video_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500]}},
            )
        except Exception:
            pass
        # Cleanup temp file if exists
        Path(temp_path).unlink(missing_ok=True)
        raise
    finally:
        sync_client.close()
