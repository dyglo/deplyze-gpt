# GitHub Repository Settings — Public Checklist

After making the repository public, enable the following settings manually in the GitHub web UI.

## 1. Secret Scanning

**Path:** Settings > Code security > Secret scanning

- [ ] Enable "Secret scanning" — GitHub will scan all pushes for known credential patterns
- [ ] Enable "Push protection" — blocks pushes that contain detected secrets before they land in history

## 2. Dependabot

**Path:** Settings > Code security > Dependabot

- [ ] Enable "Dependabot alerts" — notifies you of known vulnerabilities in dependencies
- [ ] Enable "Dependabot security updates" — automatically opens PRs to fix vulnerable dependencies
- [ ] (Optional) Enable "Dependabot version updates" — keeps dependencies current via PRs

## 3. Branch Protection (recommended)

**Path:** Settings > Branches > Add branch protection rule

For the `main` branch:

- [ ] Require a pull request before merging
- [ ] Require status checks to pass (select: `Backend Quality`, `Frontend Build`, `Workflow Lint`, `Secret Scan`)
- [ ] Do not allow bypassing the above settings

## 4. Environment + Variables

The deploy jobs reference an environment named **`production`**. Create it at:

**Path:** Settings > Environments > New environment > Name: `production`

Then add these variables either at **repository level** (Settings > Secrets and variables > Actions > Variables tab) or inside the `production` environment (both work since the deploy jobs declare `environment: production`):

| Variable | Example Value | Notes |
|----------|--------------|-------|
| `GCP_PROJECT_ID` | `your-gcp-project` | Also used as Firebase project ID, Vertex AI project, and to derive the GCS bucket |
| `CLOUD_RUN_SERVICE` | `your-api-service` | Cloud Run backend service name |
| `ARTIFACT_REGISTRY_REPO` | `your-registry` | Docker image registry name |
| `CORS_ORIGINS` | `https://your-project.web.app,https://your-domain.com` | Comma-separated allowed origins |
| `BACKEND_URL` | `https://your-api-service-xxxx.a.run.app` | Production backend URL for frontend build |

The following are **derived automatically** in the workflow and do NOT need separate variables:
- `FIREBASE_PROJECT_ID` → same as `GCP_PROJECT_ID`
- `VERTEX_AI_PROJECT` → same as `GCP_PROJECT_ID`
- `VERTEX_GCS_BUCKET` → `{GCP_PROJECT_ID}.firebasestorage.app`
- `CLOUD_RUN_REGION` → hardcoded `europe-west1`
- `VERTEX_AI_LOCATION` → hardcoded `global`
- `GEMINI_MODEL` → hardcoded `gemini-3-flash-preview`

## 5. Repository Secrets

**Path:** Settings > Secrets and variables > Actions > Secrets tab

Ensure these secrets are already configured (they should be from the existing CI/CD):

- `GCP_DEPLOYER_SERVICE_ACCOUNT_JSON`
- `FIREBASE_ADMIN_SERVICE_ACCOUNT_JSON`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `REACT_APP_FIREBASE_API_KEY`
- `REACT_APP_FIREBASE_AUTH_DOMAIN`
- `REACT_APP_FIREBASE_PROJECT_ID`
- `REACT_APP_FIREBASE_STORAGE_BUCKET`
- `REACT_APP_FIREBASE_MESSAGING_SENDER_ID`
- `REACT_APP_FIREBASE_APP_ID`
- `REACT_APP_FIREBASE_MEASUREMENT_ID`
- `LOCATE_ENDPOINT_URL`
- `LOCATE_ENDPOINT_AUDIENCE`

## 6. Visibility

**Path:** Settings > General > Danger Zone

- [ ] Change repository visibility to "Public"

Do this step **last**, after all secrets, variables, and security settings are configured.
