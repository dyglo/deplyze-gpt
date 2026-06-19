<p align="center">
  <h1 align="center">DeplyzeGPT</h1>
  <p align="center">
    <strong>Computer vision, simplified.</strong><br>
    Analyze images and videos with state-of-the-art AI models — detection, segmentation, and semantic understanding in seconds.
  </p>
</p>

<p align="center">
  <a href="https://github.com/dyglo/deplyze-gpt/stargazers"><img src="https://img.shields.io/github/stars/dyglo/deplyze-gpt?style=for-the-badge&logo=github&logoColor=white&color=orange" alt="GitHub Stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License" /></a>
  <a href="https://github.com/dyglo/deplyze-gpt/actions"><img src="https://img.shields.io/github/actions/workflow/status/dyglo/deplyze-gpt/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI" alt="CI Status" /></a>
</p>

---

## Preview

<p align="center">
  <img src="docs/screenshots/login.png" width="720" alt="Login screen" />
</p>
<p align="center">
  <img src="docs/screenshots/studio.png" width="720" alt="Studio workspace" />
</p>
<p align="center">
  <img src="docs/screenshots/model-selector.png" width="720" alt="Model selector — YOLO26, YOLO-Seg, YOLO-Sem, Gemini, Locate" />
</p>

---

## Tech Stack

<table>
  <tr>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg" width="40" height="40" alt="React" /><br><sub><b>React</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/tailwindcss/tailwindcss-original.svg" width="40" height="40" alt="Tailwind" /><br><sub><b>Tailwind</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" width="40" height="40" alt="Python" /><br><sub><b>Python</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fastapi/fastapi-original.svg" width="40" height="40" alt="FastAPI" /><br><sub><b>FastAPI</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/firebase/firebase-plain.svg" width="40" height="40" alt="Firebase" /><br><sub><b>Firebase</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/googlecloud/googlecloud-original.svg" width="40" height="40" alt="GCP" /><br><sub><b>Cloud Run</b></sub></td>
  </tr>
  <tr>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/opencv/opencv-original.svg" width="40" height="40" alt="OpenCV" /><br><sub><b>OpenCV</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/docker/docker-original.svg" width="40" height="40" alt="Docker" /><br><sub><b>Docker</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/github/github-original.svg" width="40" height="40" alt="GitHub Actions" /><br><sub><b>Actions</b></sub></td>
    <td align="center" width="96"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nodejs/nodejs-original.svg" width="40" height="40" alt="Node.js" /><br><sub><b>Node.js</b></sub></td>
    <td align="center" width="96"><img src="https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.svg" width="40" height="40" alt="YOLO" /><br><sub><b>YOLO26</b></sub></td>
    <td align="center" width="96"><img src="https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690b6.svg" width="40" height="40" alt="Gemini" /><br><sub><b>Gemini</b></sub></td>
  </tr>
</table>

<p>
  <img src="https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" />
  <img src="https://img.shields.io/badge/Python_3.14-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Firebase-DD2C00?style=flat-square&logo=firebase&logoColor=white" />
  <img src="https://img.shields.io/badge/Cloud_Run-4285F4?style=flat-square&logo=googlecloud&logoColor=white" />
  <img src="https://img.shields.io/badge/Cloudflare_R2-F38020?style=flat-square&logo=cloudflare&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/YOLO26-00FFFF?style=flat-square&logo=ultralytics&logoColor=black" />
  <img src="https://img.shields.io/badge/Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white" />
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" />
</p>

---

## Features

- **Multi-model analysis** — YOLO26 detection/segmentation, Gemini multimodal, and LocateAnything-3B visual grounding
- **Conversational UI** — chat workspace with persistent named sessions
- **Firebase Auth** — email/password authentication with email verification
- **Cloud storage** — uploads and outputs stored in Cloudflare R2 with presigned URLs
- **Session history** — full conversation persistence in Firestore with multi-turn restore
- **Video processing** — async video analysis pipeline with progress tracking
- **Smart class filtering** — natural-language YOLO class selection via Gemini

---

## Architecture

```
frontend/          React + CRA + Tailwind + shadcn/ui
                   Firebase client SDK for auth
                   Studio chat UI with sidebar sessions

backend/           FastAPI (Python)
                   Firebase Admin auth middleware
                   Firestore session/job persistence
                   Cloudflare R2 object storage (S3-compatible)
                   Gemini (Vertex AI) and YOLO26 analysis
                   LocateAnything-3B GPU worker integration

infrastructure/    Firebase Hosting (frontend)
                   Cloud Run (backend API + GPU workers)
                   Firestore (data)
                   Cloudflare R2 (file storage)
```

---

## Getting Started

### Prerequisites

- Python 3.11+ (3.14 recommended)
- Node.js 20+ (24 recommended)
- A Firebase project with Authentication and Firestore enabled
- A Firebase service account JSON with Vertex AI access
- A Cloudflare R2 bucket with S3-compatible API credentials
- FFmpeg on PATH (for video output workflows)

### 1. Clone

```bash
git clone https://github.com/dyglo/deplyze-gpt.git
cd deplyze-gpt
```

### 2. Environment Variables

```bash
cp .env.example backend/.env
```

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `R2_BUCKET_NAME` | Your Cloudflare R2 bucket name |
| `R2_ENDPOINT_URL` | R2 S3-compatible endpoint |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase Admin service account JSON |
| `VERTEX_AI_PROJECT` | Your GCP project ID |
| `VERTEX_GCS_BUCKET` | Firebase Storage bucket (`<project>.firebasestorage.app`) |
| `GEMINI_MODEL` | Gemini model name (e.g. `gemini-3-flash-preview`) |

For the frontend, create `frontend/.env`:

```dotenv
REACT_APP_FIREBASE_API_KEY=<your-firebase-web-api-key>
REACT_APP_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=<project>
REACT_APP_FIREBASE_STORAGE_BUCKET=<project>.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
REACT_APP_FIREBASE_APP_ID=<app-id>
REACT_APP_FIREBASE_MEASUREMENT_ID=<measurement-id>
REACT_APP_BACKEND_URL=http://127.0.0.1:8000
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000
```

YOLO weights (`yolo26n.pt`, `yolo26n-seg.pt`, `yolo26n-sem.pt`) download automatically on first use.

### 4. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

Opens at `http://localhost:3000`.

### 5. Firebase

Update `.firebaserc` and `firebase.json` with your Firebase project ID and Cloud Run service name, then deploy rules:

```bash
firebase deploy --only firestore:rules --project <your-project-id>
```

---

## API Reference

All `/api/*` routes require a Firebase bearer token.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload image/video to R2 |
| `POST` | `/api/analyze/image` | Run image analysis (YOLO/Gemini/LocateAnything) |
| `POST` | `/api/analyze/video` | Start async video analysis |
| `POST` | `/api/analyze/video/gemini` | Gemini video analysis |
| `GET` | `/api/analyze/video/status/{job_id}` | Poll video job status |
| `GET` | `/api/files/{type}/{job_id}/{filename}` | Serve file from R2 |
| `GET` | `/api/files/presign/{job_id}` | Get presigned output URL |
| `GET` | `/api/files/download/{job_id}` | Stream output download |
| `POST` | `/api/sessions` | Create session |
| `GET` | `/api/sessions` | List user sessions |
| `PATCH` | `/api/sessions/{session_id}` | Update session |
| `DELETE` | `/api/sessions/{session_id}` | Delete session |
| `GET` | `/api/sessions/{session_id}/messages` | List session messages |

---

## Deployment

The CI/CD pipeline (`.github/workflows/ci.yml`) handles:

1. Backend quality checks (compile + ruff lint)
2. Frontend build verification
3. Secret scanning (gitleaks)
4. Backend deployment to Cloud Run (on push to `main`)
5. Frontend deployment to Firebase Hosting (on push to `main`)

### Required Repository Variables

The CD pipeline requires these **5 GitHub Actions repository variables** to deploy. If you fork this repo, set these for your own infrastructure:

| Variable | Purpose |
|----------|---------|
| `GCP_PROJECT_ID` | GCP/Firebase project ID (also derives Vertex AI project + GCS bucket) |
| `CLOUD_RUN_SERVICE` | Cloud Run backend service name |
| `ARTIFACT_REGISTRY_REPO` | Docker Artifact Registry repository name |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins |
| `BACKEND_URL` | Production backend URL for frontend build |

Additional secrets (GCP service account, R2 credentials, Firebase config) must also be configured — see [`docs/GITHUB_PUBLIC_SETTINGS.md`](docs/GITHUB_PUBLIC_SETTINGS.md) for the full checklist.

---

## License

[MIT](LICENSE)
