# DeplyzeGPT

Computer vision studio for image and video analysis with Gemini vision, YOLO26 detection, YOLO26 instance segmentation, and YOLO26 semantic segmentation.

![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-7-47A248?logo=mongodb&logoColor=white)
![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLO26-111111)
![OpenCV](https://img.shields.io/badge/OpenCV-Video-5C3EE8?logo=opencv&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-H.264-007808?logo=ffmpeg&logoColor=white)

## Features

- Chat-style Studio UI for image and video uploads.
- Gemini text analysis for images and videos.
- YOLO26 object detection with annotated image/video output.
- YOLO26-Seg instance segmentation with visible mask overlays.
- YOLO26-Sem semantic scene segmentation with class-color overlays and legend.
- Async video jobs with progress polling, MP4 output, and download buttons.
- Annotated image download for detection, segmentation, and semantic outputs.

## Requirements

- Python 3.14+
- Node.js 24+ and npm
- Docker Desktop, for MongoDB
- FFmpeg available on `PATH`

The YOLO model weights live in `backend/`:

- `yolo26n.pt`
- `yolo26n-seg.pt`
- `yolo26n-sem.pt`

If a weight is missing, the backend attempts to download the official Ultralytics weight on first use.

## Environment

Backend environment variables:

```powershell
$env:MONGO_URL="mongodb://127.0.0.1:27017"
$env:DB_NAME="deplyzegpt"
$env:CORS_ORIGINS="*"
```

Optional Gemini support:

```powershell
$env:GEMINI_API_KEY="your-api-key"
```

Frontend environment variable:

```powershell
$env:REACT_APP_BACKEND_URL="http://127.0.0.1:8000"
```

## Start Locally

Start MongoDB:

```powershell
docker run -d --name deplyzegpt-mongo -p 127.0.0.1:27017:27017 mongo:latest
```

Install and start the backend:

```powershell
cd D:\code\vision-language\backend
pip install -r requirements.txt
$env:MONGO_URL="mongodb://127.0.0.1:27017"
$env:DB_NAME="deplyzegpt"
$env:CORS_ORIGINS="*"
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Install and start the frontend:

```powershell
cd D:\code\vision-language\frontend
npm install --legacy-peer-deps
$env:REACT_APP_BACKEND_URL="http://127.0.0.1:8000"
$env:PORT="3000"
npm start
```

Open:

```text
http://127.0.0.1:3000
```

## Test

Backend syntax check:

```powershell
cd D:\code\vision-language
python -m py_compile backend\server.py backend\video_processor.py backend\yolo_service.py
```

Frontend production build:

```powershell
cd D:\code\vision-language\frontend
npm run build
```

API health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/
```

## Notes

- Uploaded and processed files are stored under `/tmp/deplyzegpt`.
- Video processing uses OpenCV frame annotation and FFmpeg H.264 re-encoding.
- YOLO-Sem video processing is optimized for CPU by using lower inference size and capped output dimensions while keeping masks aligned frame-by-frame.
