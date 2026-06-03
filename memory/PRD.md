# DeplyzeGPT — Product Requirements Document

## Overview
**App Name:** DeplyzeGPT  
**Tagline:** Vision AI for everyone  
**Type:** Single-page Computer Vision Analysis Tool  
**Built:** June 2026

## Architecture
- **Frontend:** React 19, Tailwind CSS, Lucide icons, Outfit + JetBrains Mono fonts
- **Backend:** FastAPI (Python), MongoDB (motor async)
- **Vision AI:** Google Gemini 3-flash-preview via emergentintegrations, Ultralytics YOLO26
- **Storage:** MongoDB (metadata), /tmp/deplyzegpt/ (file storage)
- **Video:** OpenCV frame processing + FFmpeg H.264 re-encoding

## What's Been Implemented (June 2026)

### Core Features
- [x] Single-page studio layout (2-column desktop, 1-column mobile)
- [x] File upload zone (drag-drop + click) - JPEG, PNG, WEBP, MP4, MOV, AVI, max 100MB
- [x] 4 Model selector cards (gemini, yolo26, yolo26-seg, yolo26-sem)
- [x] Chat input with slash commands (/detect → yolo26, /seg → yolo26-seg)
- [x] Gemini 3-flash-preview image analysis with domain detection (medical/construction/agriculture/retail/research)
- [x] YOLO26 object detection (yolo26n.pt) - returns annotated image
- [x] YOLO26-Seg instance segmentation (yolo26n-seg.pt) - returns annotated image
- [x] YOLO26-Sem semantic segmentation (yolo26n-sem.pt) - returns annotated image
- [x] Video analysis: Gemini returns text summary
- [x] Video analysis: YOLO async job with progress polling (2s interval)
- [x] FFmpeg re-encoding (H.264, libx264, yuv420p, crf 23, faststart)
- [x] Suggestion chips after every analysis (3 clickable chips)
- [x] Job persistence banner (localStorage, 24h window)
- [x] Download video button (fetch blob, object URL, anchor trigger)
- [x] Skeleton loaders (no spinners)
- [x] Inline error handling throughout
- [x] Dark theme: #111111 bg, #1A1A1A surfaces, #C96A2A accents

### API Endpoints
- POST /api/upload — multipart file upload, returns file_url
- POST /api/analyze/image — image analysis (gemini/yolo26/yolo26-seg/yolo26-sem)
- POST /api/analyze/video — async YOLO video job, returns job_id
- GET /api/analyze/video/status/{job_id} — poll job progress
- POST /api/analyze/video/gemini — Gemini video text summary
- GET /api/files/{uploads|outputs}/{filename} — serve uploaded/processed files

## Prioritized Backlog

### P0 (Critical for production)
- Persistent file storage (S3/Firebase) — /tmp is ephemeral
- Firebase Storage migration for production video serving
- Rate limiting on upload/analyze endpoints

### P1 (Next Sprint)
- Streaming SSE for Gemini responses (real-time text generation)
- Batch image analysis (multiple files)
- Export annotated image as download
- Detection confidence slider in UI
- Video thumbnail preview

### P2 (Future)
- User accounts & analysis history
- Custom YOLO model upload
- Shareable analysis links
- Mobile app

## Next Action Items
1. Add Firebase Storage for persistent file URLs (migration path planned)
2. Implement SSE streaming for Gemini text responses
3. Add confidence threshold slider in model selector
4. Implement export annotated image feature
5. Deploy backend to Cloud Run for scalable video processing
