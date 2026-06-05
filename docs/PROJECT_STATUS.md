# DeplyzeGPT Project Status

## Summary

DeplyzeGPT is now a Firebase-authenticated computer vision studio with persistent Claude-style sessions. The app supports image/video upload, Gemini analysis, YOLO analysis, session restore, and R2-backed storage without storing presigned URLs in Firestore.

## Stack

- Frontend: React, CRA, Firebase client SDK, lucide icons.
- Backend: FastAPI, Firebase Admin SDK, Firestore, Cloudflare R2, Vertex AI SDK, OpenCV, Ultralytics.
- Auth: Firebase Auth ID tokens on all `/api/*` requests.
- Persistence: Firestore jobs, sessions, and messages.
- Object storage: Cloudflare R2 with S3-compatible API.
- Models: `gemini-3-flash-preview`, YOLO26, YOLO26-Seg, YOLO26-Sem.

## Implemented Workflows

- User signs in through Firebase Auth.
- Uploads stream to R2 under a per-user, per-session prefix.
- A session is created automatically if no `session_id` is supplied.
- Image and video analysis routes write user and assistant messages on completion.
- Video YOLO routes update Firestore job status for frontend listeners.
- Session list is shown in the sidebar, pinned first and newest first.
- Sessions can be renamed, pinned/unpinned, and deleted.
- Deleting a session deletes its messages, associated job documents, and R2 files under that session prefix.
- Session restore returns fresh one-hour presigned URLs for stored R2 paths.

## Firestore Layout

```text
jobs/{uid}/items/{job_id}
  job_id
  type
  status
  progress
  model
  session_id
  input_filename
  input_key
  output_key
  output_r2_path
  error
  created_at
  updated_at

sessions/{uid}/items/{session_id}
  session_id
  name
  model
  pinned
  created_at
  updated_at

sessions/{uid}/items/{session_id}/messages/{message_id}
  message_id
  role
  content
  input_filename
  input_r2_path
  output_r2_path
  output_type
  job_id
  model
  detections
  suggestions
  created_at
```

## R2 Layout

```text
uploads/{uid}/{session_id}/{job_id}/input.<ext>
outputs/{uid}/{session_id}/{job_id}/output.<ext>
```

Firestore stores the object path only. The backend attaches `input_url` or `output_url` when returning messages or output downloads.

## Backend Surface

Existing routes retained:

- `POST /api/upload`
- `POST /api/analyze/image`
- `POST /api/analyze/video`
- `POST /api/analyze/video/gemini`
- `GET /api/analyze/video/status/{job_id}`
- `GET /api/files/{file_type}/{job_id}/{filename}`
- `GET /api/files/presign/{job_id}`

New session routes:

- `POST /api/sessions`
- `GET /api/sessions`
- `PATCH /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/messages`

## Frontend Surface

- `Sidebar.jsx` lists sessions and owns row-level actions.
- `Studio.jsx` owns session state, active session restore, and analysis calls.
- `App.jsx` clears active-session localStorage keys on sign-out.
- Active session is stored under `deplyzegpt.activeSession.{uid}`.

## Security Rules

`firestore.rules` grants a signed-in user access only to:

```text
jobs/{uid}/items/{jobId}
sessions/{uid}/items/{sessionId}
sessions/{uid}/items/{sessionId}/messages/{messageId}
```

The rules were deployed to `projects/vision-sys/releases/cloud.firestore` during local validation.

## Local Validation Completed

- Backend compile:

```powershell
python -B -m py_compile backend\server.py backend\session_service.py backend\firestore_service.py backend\gemini_service.py
```

- Frontend production build:

```powershell
npm run build
```

- Authenticated smoke checks against the live local backend:
  - `GET /api/sessions` returned `200`.
  - `POST /api/upload` returned `200`.
  - `POST /api/analyze/image` with Gemini returned `200`.
  - `GET /api/sessions/{session_id}/messages` returned persisted messages.
  - `POST /api/analyze/video/gemini` returned `200`.

## Known Risks

- Session and message endpoints are not paginated yet.
- The delete path performs best-effort R2 cleanup and should gain retry logging for production.
- The UI has manual validation but should gain automated React tests for restore, rename, pin, and delete.
- Backend routes need integration tests with mocked Firebase/R2/Gemini dependencies.
- Video processing still runs inside the API process; a queue-backed worker would be better for production load.

## Next Recommended Work

- Add CI tests for session CRUD and message restore.
- Add pagination parameters for sessions and messages.
- Add a background queue for long-running video jobs.
- Add a production deployment runbook.
- Add observability around Gemini/R2/Firestore failures.
