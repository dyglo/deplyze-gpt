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

## 4. Repository Variables

**Path:** Settings > Secrets and variables > Actions > Variables tab

Add these repository variables (non-secret configuration):

| Variable | Example Value |
|----------|--------------|
| `GCP_PROJECT_ID` | `your-gcp-project` |
| `FIREBASE_PROJECT_ID` | `your-gcp-project` |
| `CLOUD_RUN_SERVICE` | `your-api-service` |
| `CLOUD_RUN_REGION` | `europe-west1` |
| `ARTIFACT_REGISTRY_REPO` | `your-registry` |
| `VERTEX_AI_LOCATION` | `global` |
| `VERTEX_GCS_BUCKET` | `your-project.firebasestorage.app` |
| `GEMINI_MODEL` | `gemini-3-flash-preview` |
| `CORS_ORIGINS` | `https://your-project.web.app,https://deplyzegpt.xyz` |
| `REACT_APP_BACKEND_URL` | `https://your-api-service-xxxx.a.run.app` |

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
