from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import cv2

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

UPLOADS_DIR = Path("/tmp/deplyzegpt/uploads")
OUTPUTS_DIR = Path("/tmp/deplyzegpt/outputs")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="DeplyzeGPT API")
api_router = APIRouter(prefix="/api")


class ImageAnalysisRequest(BaseModel):
    file_url: str
    model: str
    prompt: str = "Analyze this image in detail"
    confidence: float = 0.25


class VideoAnalysisRequest(BaseModel):
    file_url: str
    model: str
    confidence: float = 0.25


class VideoGeminiRequest(BaseModel):
    file_url: str
    prompt: str = "Describe what is happening in this video"


def _get_filepath(file_url: str) -> Optional[Path]:
    if "/api/files/uploads/" in file_url:
        filename = file_url.split("/api/files/uploads/")[-1]
        return UPLOADS_DIR / filename
    elif "/api/files/outputs/" in file_url:
        filename = file_url.split("/api/files/outputs/")[-1]
        return OUTPUTS_DIR / filename
    return None


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


@api_router.get("/")
async def root():
    return {"message": "DeplyzeGPT API", "status": "ok"}


@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()

    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 100MB limit")

    ct = file.content_type or ""
    fname = file.filename or "upload"
    ext = Path(fname).suffix.lower()

    is_image = ct.startswith("image/") or ext in ['.jpg', '.jpeg', '.png', '.webp']
    is_video = ct.startswith("video/") or ext in ['.mp4', '.mov', '.avi']

    if not (is_image or is_video):
        raise HTTPException(400, "Unsupported file type. Only image/video files accepted.")

    file_id = str(uuid.uuid4())
    safe_ext = ext if ext else (".jpg" if is_image else ".mp4")
    filename = f"{file_id}{safe_ext}"
    filepath = UPLOADS_DIR / filename

    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "file_id": file_id,
        "url": f"/api/files/uploads/{filename}",
        "filename": fname,
        "file_type": "image" if is_image else "video",
        "size": len(content),
        "content_type": ct,
    }


@api_router.get("/files/{file_type}/{filename}")
async def serve_file(file_type: str, filename: str):
    if file_type == "uploads":
        filepath = UPLOADS_DIR / filename
    elif file_type == "outputs":
        filepath = OUTPUTS_DIR / filename
    else:
        raise HTTPException(404, "Invalid file type")

    if not filepath.exists():
        raise HTTPException(404, "File not found")

    headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"}
    if file_type == "outputs":
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(str(filepath), headers=headers)


@api_router.post("/analyze/image")
async def analyze_image(request: ImageAnalysisRequest):
    filepath = _get_filepath(request.file_url)
    if not filepath or not filepath.exists():
        raise HTTPException(404, "File not found")

    try:
        if request.model == "gemini":
            from gemini_service import analyze_image_gemini
            return await analyze_image_gemini(str(filepath), request.prompt)
        else:
            from yolo_service import analyze_image_yolo
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor, analyze_image_yolo, str(filepath), request.model, request.confidence
            )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis failed: {str(e)[:300]}")


@api_router.post("/analyze/video")
async def analyze_video(request: VideoAnalysisRequest, background_tasks: BackgroundTasks):
    if request.model == "gemini":
        raise HTTPException(400, "Use /api/analyze/video/gemini for Gemini video analysis")

    filepath = _get_filepath(request.file_url)
    if not filepath or not filepath.exists():
        raise HTTPException(404, "File not found")

    from yolo_service import MODEL_MAP, ensure_model_available
    if request.model not in MODEL_MAP:
        raise HTTPException(422, f"Unsupported video model: {request.model}")
    try:
        await asyncio.get_event_loop().run_in_executor(executor, ensure_model_available, request.model)
    except Exception:
        raise HTTPException(
            422,
            f"Model {request.model} could not be downloaded for video processing. Try again later.",
        )

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.video_jobs.insert_one({
        "job_id": job_id,
        "status": "queued",
        "model": request.model,
        "progress": 0,
        "output_url": None,
        "error": None,
        "created_at": now,
    })

    background_tasks.add_task(
        _run_video_job, job_id, str(filepath), request.model, request.confidence
    )

    return {"job_id": job_id}


@api_router.get("/analyze/video/status/{job_id}")
async def get_video_status(job_id: str):
    job = await db.video_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@api_router.post("/analyze/video/gemini")
async def analyze_video_gemini_route(request: VideoGeminiRequest):
    filepath = _get_filepath(request.file_url)
    if not filepath or not filepath.exists():
        raise HTTPException(404, "File not found")

    try:
        from gemini_service import analyze_video_gemini
        return await analyze_video_gemini(str(filepath), request.prompt)
    except Exception as e:
        logger.error(f"Gemini video error: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis failed: {str(e)[:300]}")


async def _run_video_job(job_id: str, video_path: str, model_type: str, confidence: float):
    try:
        from video_processor import process_video_yolo
        loop = asyncio.get_event_loop()
        duration_seconds = _get_video_duration_seconds(video_path)
        timeout_multiplier = 20 if model_type == "yolo26-sem" else 4
        timeout_floor = 1200 if model_type == "yolo26-sem" else 600
        timeout_seconds = max(timeout_floor, int(duration_seconds * timeout_multiplier))
        output_path = await asyncio.wait_for(
            loop.run_in_executor(executor, process_video_yolo, job_id, video_path, model_type, confidence, OUTPUTS_DIR),
            timeout=timeout_seconds,
        )
        output_url = f"/api/files/outputs/{Path(output_path).name}"
        await db.video_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "done", "progress": 100, "output_url": output_url}},
        )
    except asyncio.TimeoutError:
        await db.video_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "error": "Processing timeout exceeded"}},
        )
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        await db.video_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "error": str(e)[:500]}},
        )


async def _prewarm_models():
    """Load YOLO models into memory at startup to avoid first-request cold start."""
    loop = asyncio.get_event_loop()
    for model_type in ['yolo26', 'yolo26-seg']:
        try:
            from yolo_service import get_model
            await loop.run_in_executor(executor, get_model, model_type)
            logger.info(f"Pre-warmed YOLO model: {model_type}")
        except Exception as e:
            logger.warning(f"Pre-warm skipped for {model_type}: {e}")


@app.on_event("startup")
async def startup():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.create_task(_prewarm_models())
    logger.info("DeplyzeGPT API started")


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
