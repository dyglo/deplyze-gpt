import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import requests
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from PIL import Image
from transformers import AutoModel, AutoProcessor, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = os.environ.get("LOCATE_MODEL_PATH") or (
    "/repository" if os.path.exists("/repository") else "nvidia/LocateAnything-3B"
)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if torch.cuda.is_available() else torch.float32
SUPPORTED_GENERATION_MODES = {"fast", "slow", "hybrid"}
DEFAULT_MAX_NEW_TOKENS = 8192
DEFAULT_MAX_IMAGE_SIDE = 1024
WORKER_BACKEND = os.environ.get("LOCATE_WORKER_BACKEND", "raw").strip().lower()
OPENAI_BASE_URL = os.environ.get("LOCATE_OPENAI_BASE_URL", "").strip().rstrip("/")
OPENAI_API_KEY = os.environ.get("LOCATE_OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("LOCATE_OPENAI_MODEL", MODEL_ID)
RAW_BATCH_SEQUENTIAL = os.environ.get("LOCATE_RAW_BATCH_SEQUENTIAL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class PredictRequest(BaseModel):
    image_b64: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    generation_mode: str = "hybrid"
    max_new_tokens: int = Field(DEFAULT_MAX_NEW_TOKENS, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class PredictResponse(BaseModel):
    answer: str
    mode: str
    timings: dict[str, float]
    stats: Optional[Any] = None
    backend: str = WORKER_BACKEND


class BatchFrameRequest(BaseModel):
    frame_id: str = Field(..., min_length=1)
    image_b64: str = Field(..., min_length=1)
    timestamp_seconds: Optional[float] = None


class PredictBatchRequest(BaseModel):
    frames: list[BatchFrameRequest] = Field(..., min_length=1, max_length=48)
    prompt: str = Field(..., min_length=1)
    generation_mode: str = "hybrid"
    max_new_tokens: int = Field(DEFAULT_MAX_NEW_TOKENS, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class BatchFrameResponse(BaseModel):
    frame_id: str
    answer: str
    mode: str
    timings: dict[str, float]
    stats: Optional[Any] = None
    model: str = MODEL_ID


class PredictBatchResponse(BaseModel):
    results: list[BatchFrameResponse]
    batch_size: int
    backend: str


class ModelNotLoadedError(RuntimeError):
    pass


def _max_image_side() -> int:
    try:
        value = int(os.environ.get("LOCATE_WORKER_MAX_IMAGE_SIDE", str(DEFAULT_MAX_IMAGE_SIDE)))
    except ValueError:
        value = DEFAULT_MAX_IMAGE_SIDE
    return max(256, value)


class LocateAnythingWorker:
    def __init__(self, model_path: str, device: str = DEVICE, dtype: torch.dtype = DTYPE):
        self.model_path = model_path
        self.device = device
        self.dtype = dtype
        self.tokenizer = None
        self.processor = None
        self.model = None

    async def load(self):
        if self.model is not None:
            return
        if self.device != "cuda":
            raise RuntimeError("LocateAnything requires an NVIDIA GPU; CUDA is not available.")

        start = time.perf_counter()
        logger.info("Loading LocateAnything model from %s", self.model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        self.processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            self.model_path,
            torch_dtype=self.dtype,
            trust_remote_code=True,
        ).to(self.device).eval()
        logger.info("LocateAnything model ready in %.2fs", time.perf_counter() - start)

    async def unload(self):
        if self.model is not None:
            self.model.to("cpu")
            del self.model
            self.model = None
        self.tokenizer = None
        self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get(self):
        if self.model is None or self.tokenizer is None or self.processor is None:
            raise ModelNotLoadedError("Model not loaded")
        return self.model, self.tokenizer, self.processor

    @torch.no_grad()
    def predict(
        self,
        image: Image.Image,
        prompt: str,
        generation_mode: str,
        max_new_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        model, tokenizer, processor = self.get()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = processor.py_apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images, videos = processor.process_vision_info(messages)
        inputs = processor(text=[text], images=images, videos=videos, return_tensors="pt").to(self.device)
        pixel_values = inputs["pixel_values"].to(self.dtype)
        response = model.generate(
            pixel_values=pixel_values,
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            image_grid_hws=inputs.get("image_grid_hws", None),
            tokenizer=tokenizer,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            generation_mode=generation_mode,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.1,
            verbose=False,
        )

        result = {"answer": response[0] if isinstance(response, tuple) else response}
        if isinstance(response, tuple) and len(response) >= 3:
            result["stats"] = response[2]
        return result


worker = LocateAnythingWorker(MODEL_ID)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if WORKER_BACKEND == "raw":
        await worker.load()
    elif WORKER_BACKEND in {"openai", "vllm", "sglang"}:
        if not OPENAI_BASE_URL:
            raise RuntimeError("LOCATE_OPENAI_BASE_URL is required for OpenAI-compatible Locate worker mode.")
        logger.info("LocateAnything worker using %s backend at %s", WORKER_BACKEND, OPENAI_BASE_URL)
    else:
        raise RuntimeError("LOCATE_WORKER_BACKEND must be raw, openai, vllm, or sglang.")
    try:
        yield
    finally:
        if WORKER_BACKEND == "raw":
            await worker.unload()


app = FastAPI(title="DeplyzeGPT LocateAnything Worker", lifespan=lifespan)


def _decode_image(image_b64: str) -> Image.Image:
    try:
        payload = image_b64.split(",", 1)[1] if image_b64.startswith("data:") else image_b64
        image = Image.open(io.BytesIO(base64.b64decode(payload))).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid image_b64 payload") from exc

    max_side = _max_image_side()
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image

    scale = max_side / longest
    return image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS,
    )


def _openai_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    return headers


def _openai_chat_url() -> str:
    base = OPENAI_BASE_URL.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _openai_predict(image_b64: str, prompt: str, max_new_tokens: int, temperature: float) -> dict[str, Any]:
    start = time.perf_counter()
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": max_new_tokens,
        "temperature": temperature,
    }
    response = requests.post(_openai_chat_url(), json=payload, headers=_openai_headers(), timeout=600)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI-compatible Locate backend returned {response.status_code}: {response.text[:300]}")
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI-compatible Locate backend returned no choices")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    return {
        "answer": content,
        "timings": {"total_seconds": round(time.perf_counter() - start, 3)},
        "stats": {"usage": data.get("usage")},
    }


@app.get("/health")
def health():
    if WORKER_BACKEND == "raw":
        try:
            worker.get()
        except ModelNotLoadedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE, "backend": WORKER_BACKEND}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    mode = payload.generation_mode.strip().lower()
    if mode not in SUPPORTED_GENERATION_MODES:
        raise HTTPException(status_code=422, detail="generation_mode must be fast, slow, or hybrid")

    image = _decode_image(payload.image_b64)
    start = time.perf_counter()
    try:
        if WORKER_BACKEND == "raw":
            result = worker.predict(
                image=image,
                prompt=payload.prompt,
                generation_mode=mode,
                max_new_tokens=payload.max_new_tokens,
                temperature=payload.temperature,
            )
        else:
            jpeg = io.BytesIO()
            image.save(jpeg, format="JPEG", quality=95)
            result = _openai_predict(
                base64.b64encode(jpeg.getvalue()).decode("utf-8"),
                payload.prompt,
                payload.max_new_tokens,
                payload.temperature,
            )
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.exception("LocateAnything generation failed")
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return PredictResponse(
        answer=str(result.get("answer", "")),
        mode=mode,
        timings={"total_seconds": round(time.perf_counter() - start, 3)},
        stats=result.get("stats"),
        backend=WORKER_BACKEND,
    )


@app.post("/predict_batch", response_model=PredictBatchResponse)
def predict_batch(payload: PredictBatchRequest):
    mode = payload.generation_mode.strip().lower()
    if mode not in SUPPORTED_GENERATION_MODES:
        raise HTTPException(status_code=422, detail="generation_mode must be fast, slow, or hybrid")
    if WORKER_BACKEND == "raw" and len(payload.frames) > 1 and not RAW_BATCH_SEQUENTIAL:
        raise HTTPException(
            status_code=501,
            detail=(
                "Raw LocateAnything Transformers generate is batch-size-one. "
                "Use LOCATE_WORKER_BACKEND=vllm or sglang for video batch inference."
            ),
        )

    def run_one(frame: BatchFrameRequest) -> BatchFrameResponse:
        start = time.perf_counter()
        image = _decode_image(frame.image_b64)
        if WORKER_BACKEND == "raw":
            result = worker.predict(
                image=image,
                prompt=payload.prompt,
                generation_mode=mode,
                max_new_tokens=payload.max_new_tokens,
                temperature=payload.temperature,
            )
        else:
            jpeg = io.BytesIO()
            image.save(jpeg, format="JPEG", quality=95)
            result = _openai_predict(
                base64.b64encode(jpeg.getvalue()).decode("utf-8"),
                payload.prompt,
                payload.max_new_tokens,
                payload.temperature,
            )
        timings = dict(result.get("timings") or {})
        timings.setdefault("total_seconds", round(time.perf_counter() - start, 3))
        return BatchFrameResponse(
            frame_id=frame.frame_id,
            answer=str(result.get("answer", "")),
            mode=mode,
            timings=timings,
            stats=result.get("stats"),
            model=OPENAI_MODEL if WORKER_BACKEND != "raw" else MODEL_ID,
        )

    try:
        if WORKER_BACKEND == "raw":
            results = [run_one(frame) for frame in payload.frames]
        else:
            max_workers = min(len(payload.frames), int(os.environ.get("LOCATE_OPENAI_BATCH_CONCURRENCY", "4")))
            ordered: dict[str, BatchFrameResponse] = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(run_one, frame): frame.frame_id for frame in payload.frames}
                for future in as_completed(futures):
                    ordered[futures[future]] = future.result()
            results = [ordered[frame.frame_id] for frame in payload.frames]
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.exception("LocateAnything batch generation failed")
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {exc}") from exc
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return PredictBatchResponse(
        results=results,
        batch_size=len(results),
        backend=WORKER_BACKEND,
    )
