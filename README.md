# DeplyzeGPT

DeplyzeGPT is an authenticated computer vision studio for image and video analysis. It combines a Claude-style React workspace, a FastAPI backend, Firebase Auth, Firestore session history, Cloudflare R2 object storage, Gemini multimodal analysis, and YOLO26 detection/segmentation models.

## Current Capabilities

- Firebase-authenticated Studio UI.
- Image and video uploads streamed to Cloudflare R2.
- Upload progress in the frontend.
- Persistent named sessions stored per user in Firestore.
- Sidebar session list with newest-first ordering, pinned sessions, rename, pin/unpin, and delete.
- Full multi-turn conversation restore from Firestore.
- Fresh one-hour R2 presigned URLs generated when session messages are read.
- Gemini image and video analysis with Vertex AI `gemini-3-flash-preview`.
- YOLO26 object detection, instance segmentation, and semantic segmentation.
- Firestore-backed video job status updates.

## Architecture

```text
frontend/
  React + CRA + Firebase client SDK
  Auth, Studio chat UI, persistent sidebar sessions

backend/
  FastAPI
  Firebase Admin auth middleware
  Firestore job/session persistence
  Cloudflare R2 object storage
  Gemini and YOLO analysis routes

firestore.rules
  Per-user access for jobs and sessions
```

## Data Model

Firestore session documents:

```text
sessions/{uid}/items/{session_id}
  name
  model
  pinned
  created_at
  updated_at
```

Firestore message documents:

```text
sessions/{uid}/items/{session_id}/messages/{message_id}
  role
  content
  input_filename
  input_r2_path
  output_r2_path
  output_type
  job_id
  model
  created_at
```

Firestore job documents:

```text
jobs/{uid}/items/{job_id}
```

R2 object paths are stored in Firestore. Presigned URLs are never stored; the backend creates fresh read URLs when messages or outputs are requested.

## Requirements

- Windows PowerShell, or equivalent shell with command adjustments.
- Python available at `C:\Python314\python.exe` for the current local setup.
- Node.js and npm.
- Firebase project with Auth and Firestore enabled.
- Firebase service account JSON in the repo root, or `FIREBASE_SERVICE_ACCOUNT_PATH` pointing to it.
- Cloudflare R2 bucket and S3-compatible access keys.
- Gemini API key.
- FFmpeg on `PATH` for video output workflows.

YOLO weights are expected in `backend/` or downloaded on first use:

- `yolo26n.pt`
- `yolo26n-seg.pt`
- `yolo26n-sem.pt`

## Environment

Create `backend/.env`:

```dotenv
R2_BUCKET_NAME=deplyzegpt-storage
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<r2-access-key-id>
R2_SECRET_ACCESS_KEY=<r2-secret-access-key>

FIREBASE_SERVICE_ACCOUNT_PATH=../vision-sys-firebase-adminsdk-example.json

VERTEX_AI_PROJECT=vision-sys
VERTEX_AI_LOCATION=global
VERTEX_GCS_BUCKET=vision-sys.firebasestorage.app
GEMINI_MODEL=gemini-3-flash-preview
```

Create `frontend/.env`:

```dotenv
REACT_APP_FIREBASE_API_KEY=<firebase-web-api-key>
REACT_APP_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=<project>
REACT_APP_FIREBASE_STORAGE_BUCKET=<project>.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
REACT_APP_FIREBASE_APP_ID=<app-id>
REACT_APP_FIREBASE_MEASUREMENT_ID=<measurement-id>
REACT_APP_BACKEND_URL=http://127.0.0.1:8000
```

Do not commit real `.env` files, Firebase service account JSON, R2 keys, or API keys.

## Start Locally

Backend:

```powershell
cd D:\code\vision-language\backend
C:\Python314\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd D:\code\vision-language\frontend
npm install --legacy-peer-deps
npm start
```

Open the frontend URL shown by CRA, usually:

```text
http://localhost:3000
```

If CRA asks to use `3001`, accept it. The backend allows both `localhost` and `127.0.0.1` on ports `3000` and `3001`.

## API Routes

Existing route paths are kept stable:

- `POST /api/upload`
- `POST /api/analyze/image`
- `POST /api/analyze/video`
- `POST /api/analyze/video/gemini`
- `GET /api/analyze/video/status/{job_id}`
- `GET /api/files/{file_type}/{job_id}/{filename}`
- `GET /api/files/presign/{job_id}`

Session routes:

- `POST /api/sessions`
- `GET /api/sessions`
- `PATCH /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/messages`

All `/api/*` routes require a Firebase bearer token from the frontend.

## Firestore Rules

Rules live in `firestore.rules` and allow each authenticated user to read and write only their own job and session documents:

```text
jobs/{uid}/items/{jobId}
sessions/{uid}/items/{sessionId}
sessions/{uid}/items/{sessionId}/messages/{messageId}
```

Deploy rules with your Firebase workflow before testing a new project environment.

## Validation

Backend compile check:

```powershell
cd D:\code\vision-language
python -B -m py_compile backend\server.py backend\session_service.py backend\firestore_service.py backend\gemini_service.py
```

Frontend build:

```powershell
cd D:\code\vision-language\frontend
npm run build
```

Manual smoke flow:

1. Start backend and frontend.
2. Sign in.
3. Upload an image.
4. Ask a Gemini question.
5. Confirm a session appears in the sidebar.
6. Refresh the browser.
7. Confirm the active session and conversation restore.
8. Upload a video and run Gemini or YOLO analysis.

## Common Local Issues

- `No module named cv2`: use the Python environment that has `opencv-python` installed, or install `backend/requirements.txt`.
- `WinError 10048`: port `8000` is already in use. Stop the existing backend process before starting another one.
- `/api/sessions` returns `401`: expected when no Firebase bearer token is sent.
- `/api/sessions` returns `404`: the backend process is stale or running from the wrong folder. Restart `uvicorn` from `backend/`.
- Vertex Gemini authentication fails locally: confirm `FIREBASE_SERVICE_ACCOUNT_PATH` points to a service account with Vertex AI access.

## Production Notes

- Keep all secrets out of git.
- Store only R2 object paths in Firestore.
- Generate presigned URLs on read with short expiry.
- Delete session-owned R2 prefixes when deleting a session.
- Add pagination before large session/message histories.
- Add CI tests for auth, sessions, upload, and Gemini/YOLO route contracts before scaling usage.
