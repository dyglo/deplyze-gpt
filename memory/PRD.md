# DeplyzeGPT — Product Requirements Document

## Overview
**App Name:** DeplyzeGPT  
**Tagline:** Vision AI for everyone  
**Type:** Single-page Computer Vision Analysis Tool  
**Built:** June 2026

## Architecture
- **Frontend:** React 19, Tailwind CSS, Lucide icons, Outfit font
- **Backend:** FastAPI (Python), MongoDB (motor async)
- **Vision AI:** Google Gemini 3-flash-preview via emergentintegrations, Ultralytics YOLO26
- **Storage:** MongoDB (metadata), /tmp/deplyzegpt/ (file storage)
- **Video:** OpenCV frame processing + FFmpeg H.264 re-encoding

## UI Layout (Claude.ai-style Chat Interface)
- **Left sidebar (52px):** Eye logo, New Chat (+) button, History placeholder, Settings placeholder
- **Header:** DeplyzeGPT brand + "Free" badge
- **Chat area:** Scrollable conversation with user bubbles (right) and assistant bubbles (left)
- **Empty state:** Centered greeting "What would you like to analyze today?" + suggestion chips
- **Input bar:** Paperclip (attach) + Textarea + Model dropdown + Send button

## Component Architecture
```
/app/frontend/src/components/
  Studio.jsx         - Main orchestrator (state, API calls, layout)
  Sidebar.jsx        - Left sidebar (new chat, placeholders)
  ChatMessages.jsx   - Chat bubbles (user + assistant), empty state
  ChatInputBar.jsx   - Input, file attach, model dropdown, send
  [legacy - unused]
  UploadZone.jsx
  ModelSelector.jsx
  ChatInput.jsx
  OutputPanel.jsx
```

## What's Been Implemented (June 2026)

### Core Features
- [x] Claude.ai-style chat interface (redesigned June 2026)
- [x] Left sidebar with new chat button + placeholder icons for future expansion
- [x] Instant file attachment: thumbnail shows immediately while upload happens in background
- [x] Chat conversation: user messages (right-aligned) + assistant responses (left-aligned)
- [x] Model selector dropdown in input bar (4 models: Gemini, YOLO26, YOLO-Seg, YOLO-Sem)
- [x] Empty state greeting with quick suggestion chips
- [x] 4 models: gemini (Gemini 3-flash), yolo26, yolo26-seg, yolo26-sem
- [x] YOLO model pre-warming at startup (no cold-start 502 errors)
- [x] Graceful error for missing yolo26-sem model (returns 404 with clear message)
- [x] Gemini 3-flash-preview image + video analysis
- [x] YOLO26 object detection (yolo26n.pt)
- [x] YOLO26-Seg instance segmentation (yolo26n-seg.pt)
- [x] Video analysis: Gemini returns text summary
- [x] Video analysis: YOLO async job with progress polling
- [x] FFmpeg re-encoding (H.264)
- [x] Suggestion chips after every analysis (clickable, fills prompt input)
- [x] Download video button
- [x] Detection badge showing class counts after YOLO analysis

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
- Rate limiting on upload/analyze endpoints

### P1 (Next Sprint)
- Firebase Storage migration for permanent file URLs
- Add yolo26-sem model weights when available
- Streaming SSE for Gemini responses (real-time text generation)
- Batch image analysis (multiple files)
- Export annotated image as download
- Detection confidence slider

### P2 (Future)
- Chat history persistence per session
- User accounts & analysis history
- Custom YOLO model upload
- Shareable analysis links
- Mobile app
