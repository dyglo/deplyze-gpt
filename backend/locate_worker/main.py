import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

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
    await worker.load()
    try:
        yield
    finally:
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


@app.get("/health")
def health():
    try:
        worker.get()
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    mode = payload.generation_mode.strip().lower()
    if mode not in SUPPORTED_GENERATION_MODES:
        raise HTTPException(status_code=422, detail="generation_mode must be fast, slow, or hybrid")

    image = _decode_image(payload.image_b64)
    start = time.perf_counter()
    try:
        result = worker.predict(
            image=image,
            prompt=payload.prompt,
            generation_mode=mode,
            max_new_tokens=payload.max_new_tokens,
            temperature=payload.temperature,
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
    )
