# Google Cloud Run — Deployment Guide

This guide walks you through deploying the Multi-Agent AI Productivity System
to **Google Cloud Run** using Docker.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Google Cloud SDK (`gcloud`) | Latest |
| Docker | 20+ |
| A GCP project with billing enabled | — |

---

## Step 1 — Set up GCP project

```bash
# Authenticate
gcloud auth login

# Set your project
export PROJECT_ID=your-gcp-project-id
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

---

## Step 2 — Store secrets in Secret Manager

Never put API keys in environment variables directly.

```bash
# OpenAI API key
echo -n "sk-your-openai-key" | \
  gcloud secrets create OPENAI_API_KEY --data-file=-

# MongoDB URI (use MongoDB Atlas for production)
echo -n "mongodb+srv://user:pass@cluster.mongodb.net/multi_agent_db" | \
  gcloud secrets create MONGODB_URI --data-file=-

# Application secret key
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create SECRET_KEY --data-file=-
```

---

## Step 3 — Create Artifact Registry repository

```bash
export REGION=us-central1
export REPO=multi-agent-repo

gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="Multi-Agent AI System"
```

---

## Step 4 — Build and push Docker image

```bash
export IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/multi-agent-app:latest

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build image (multi-platform for Cloud Run)
docker buildx build \
  --platform linux/amd64 \
  -t $IMAGE \
  --push \
  .
```

---

## Step 5 — Deploy to Cloud Run

```bash
gcloud run deploy multi-agent-app \
  --image=$IMAGE \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300 \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest,MONGODB_URI=MONGODB_URI:latest,SECRET_KEY=SECRET_KEY:latest" \
  --set-env-vars="OPENAI_MODEL=gpt-4o,APP_ENV=production,SCHEDULER_TIMEZONE=UTC"
```

---

## Step 6 — Verify deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe multi-agent-app \
  --platform managed --region $REGION \
  --format 'value(status.url)')

echo "Service URL: $SERVICE_URL"

# Health check
curl "$SERVICE_URL/health"
# Expected: {"status":"healthy"}

# Test the AI endpoint
curl -X POST "$SERVICE_URL/query/" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "query": "What should I do today?"}'
```

---

## Step 7 — (Optional) Set up MongoDB Atlas

For production, use [MongoDB Atlas](https://www.mongodb.com/atlas) instead
of a self-hosted instance:

1. Create a free M0 cluster on Atlas.
2. Whitelist Cloud Run's egress IPs (or allow all: `0.0.0.0/0` for dev).
3. Get the connection string:
   `mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/multi_agent_db`
4. Update the `MONGODB_URI` secret.

---

## CI/CD with Cloud Build (optional)

Create `cloudbuild.yaml` in the repo root:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$_IMAGE', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '$_IMAGE']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - multi-agent-app
      - --image=$_IMAGE
      - --region=$_REGION
      - --platform=managed

substitutions:
  _IMAGE: 'us-central1-docker.pkg.dev/YOUR_PROJECT/multi-agent-repo/multi-agent-app:$COMMIT_SHA'
  _REGION: 'us-central1'
```

Trigger on push to `main`:
```bash
gcloud builds triggers create github \
  --repo-name=multi-agent \
  --repo-owner=your-github-handle \
  --branch-pattern=main \
  --build-config=cloudbuild.yaml
```

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | *required* |
| `OPENAI_MODEL` | Model name | `gpt-4o` |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `multi_agent_db` |
| `APP_ENV` | Environment (`development`/`production`) | `development` |
| `SCHEDULER_TIMEZONE` | Timezone for APScheduler | `UTC` |
| `DEADLINE_CHECK_INTERVAL_MINUTES` | How often to check deadlines | `30` |
| `FAISS_INDEX_PATH` | Path to persist FAISS index | `./data/faiss_index` |
| `OVERDUE_WARNING_HOURS` | Hours before deadline to warn | `24` |
| `OVERLOAD_TASK_THRESHOLD` | Max tasks before overload warning | `10` |

---

## Cost Estimation (Cloud Run)

| Resource | Approximate cost |
|----------|-----------------|
| 1M requests/month | ~$0.40 |
| 2 GiB memory / 2 vCPU | ~$0.00 (free tier) to ~$15/month |
| MongoDB Atlas M0 | **Free** |

Total for a moderate workload: **< $5/month**.
