# DealFrame Deployment Guide

## Quick Start (Docker Compose)

The fastest way to get DealFrame running:

```bash
# Clone and configure
git clone <repo-url> && cd DealFrame
cp .env.example .env   # Edit with your keys

# Launch all services
docker compose up -d

# Verify
curl http://localhost:8000/health
```

Services:
| Service   | Port   | Description                    |
|-----------|--------|--------------------------------|
| app       | 8000   | FastAPI backend                |
| frontend  | 3000   | React dashboard                |
| postgres  | 5432   | PostgreSQL database            |

---

## Environment Variables

### Required

| Variable         | Description                              | Example                                         |
|-----------------|-------------------------------------------|-------------------------------------------------|
| `DATABASE_URL`  | PostgreSQL connection string              | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `SECRET_KEY`    | JWT signing key                           | (generate with `openssl rand -hex 32`)          |

### Optional — Integrations

| Variable              | Description                         | Default       |
|-----------------------|-------------------------------------|---------------|
| `DEEPGRAM_API_KEY`    | Deepgram streaming ASR              | _(disabled)_  |
| `OPENAI_API_KEY`      | GPT-4o vision analysis              | _(disabled)_  |
| `STORAGE_BACKEND`     | `local` or `s3`                     | `local`       |
| `S3_BUCKET`           | S3/MinIO bucket name                | `temporalos`  |
| `S3_ENDPOINT_URL`     | MinIO endpoint (local dev)          | _(none)_      |
| `S3_REGION`           | AWS region                          | `us-east-1`   |
| `SALESFORCE_CLIENT_ID`| Salesforce CRM integration          | _(disabled)_  |
| `HUBSPOT_API_KEY`     | HubSpot CRM integration            | _(disabled)_  |
| `SLACK_BOT_TOKEN`     | Slack notifications                 | _(disabled)_  |

---

## Database Setup

### Run Migrations

```bash
# Using Alembic (directly)
alembic upgrade head

# Using Make
make migrate
```

### Seed Demo Data

```bash
python -m temporalos.scripts.seed_demo
```

---

## Local Development (without Docker)

### Prerequisites
- Python 3.12+
- Node.js 20+
- FFmpeg
- PostgreSQL 15+ (or use SQLite for dev)

### Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run with SQLite for local dev
export DATABASE_URL="sqlite+aiosqlite:///./dev.db"
alembic upgrade head
uvicorn temporalos.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite dev server on :3000
```

---

## Production Deployment

### Health Probes

Configure your orchestrator health checks:

| Probe      | Endpoint          | Purpose                         |
|------------|-------------------|---------------------------------|
| Liveness   | `GET /health/live`  | App is running (restart if fails) |
| Readiness  | `GET /health/ready` | App can serve traffic (DB connected) |
| Startup    | `GET /health`       | Basic health check              |

### Security Headers

The API automatically sets these headers on every response:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy`

### Reverse Proxy (Nginx)

```nginx
upstream temporalos_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl;
    server_name temporalos.example.com;

    ssl_certificate     /etc/letsencrypt/live/temporalos.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/temporalos.example.com/privkey.pem;

    location /api/ {
        proxy_pass http://temporalos_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://temporalos_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        root /var/www/temporalos/frontend/dist;
        try_files $uri /index.html;
    }
}
```

---

## Storage Configuration

### Local (default)
Files stored at `./uploads/`. Set:
```bash
STORAGE_BACKEND=local
```

### S3 / MinIO
```bash
STORAGE_BACKEND=s3
S3_BUCKET=temporalos
S3_REGION=us-east-1

# For MinIO local dev:
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
```

---

## Running Tests

```bash
# Unit tests
make test

# End-to-end tests
make test-e2e

# Full suite with coverage
pytest --cov=temporalos --cov-report=html
```

---

## Monitoring

DealFrame includes built-in OpenTelemetry instrumentation:
- **Metrics**: Pipeline latency, extraction accuracy, segment counts
- **Traces**: Full request tracing across processing stages
- **Drift Detection**: Automatic alerts when model output distribution shifts

Configure a Prometheus/Grafana stack or OTLP-compatible collector:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```
