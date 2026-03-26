# DealFrame Architecture

## System Overview

DealFrame is a **Video → Structured Negotiation Intelligence Engine**. It processes sales calls, demos, and walkthroughs into machine-consumable structured intelligence — segments with topics, sentiment, risk scores, objections, decision signals, and intent.

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Dashboard (:3000)                  │
│  25 pages · TailwindCSS · Vite · Real-time WebSocket updates    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST + WS
┌──────────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend (:8000)                       │
│  28 route modules · Security headers · Health probes            │
├─────────┬──────────┬──────────┬──────────┬──────────┬───────────┤
│ Process │ Intelli- │ Observa- │ Agent    │ Platform │ Enterprise│
│ Engine  │ gence    │ bility   │ Layer    │ Services │ Features  │
└────┬────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴─────┬────┘
     │         │          │          │          │           │
     ▼         ▼          ▼          ▼          ▼           ▼
 ┌───────┐ ┌───────┐ ┌────────┐ ┌───────┐ ┌────────┐ ┌─────────┐
 │FFmpeg │ │Pattern│ │OpenTel │ │Multi- │ │Auth    │ │Vertical │
 │Whisper│ │Mining │ │Drift   │ │Agent  │ │RBAC    │ │Packs    │
 │Vision │ │Diff   │ │Metrics │ │Copilot│ │Tenants │ │Workflow │
 │OCR    │ │Copilot│ │Logging │ │RAG    │ │Audit   │ │Playbooks│
 └───┬───┘ └───────┘ └────────┘ └───────┘ └───┬────┘ └─────────┘
     │                                         │
     ▼                                         ▼
 ┌────────────────┐                    ┌──────────────┐
 │ Storage Layer  │                    │ PostgreSQL   │
 │ Local / S3     │                    │ (Alembic)    │
 └────────────────┘                    └──────────────┘
```

---

## Module Map

### Processing Pipeline (`temporalos/pipeline/`, `ingestion/`, `audio/`, `vision/`)
| Module        | Purpose |
|---------------|---------|
| `ingestion`   | File upload, format detection, FFmpeg frame extraction |
| `audio`       | Whisper/Deepgram ASR, streaming transcription, diarization |
| `vision`      | Slide/screen detection, OCR, visual feature extraction |
| `alignment`   | Frame ↔ transcript temporal alignment |
| `pipeline`    | Orchestrates full processing: ingest → transcribe → align → extract |

### Intelligence (`temporalos/intelligence/`, `extraction/`, `search/`)
| Module          | Purpose |
|-----------------|---------|
| `extraction`    | Structured extraction — objections, intent, risk, decision signals |
| `intelligence`  | Pattern mining, call diffing, live copilot coaching |
| `search`        | Semantic search with vector embeddings across all processed content |
| `summarization` | Segment and full-call summarization |

### Observability (`temporalos/observability/`, `observatory/`)
| Module          | Purpose |
|-----------------|---------|
| `observability` | OpenTelemetry tracing, Prometheus metrics, pipeline telemetry |
| `observatory`   | Drift detection, accuracy tracking, model monitoring dashboard |

### Platform (`temporalos/auth/`, `db/`, `notifications/`, `storage/`)
| Module          | Purpose |
|-----------------|---------|
| `auth`          | JWT authentication, RBAC (admin/analyst/viewer), tenant isolation |
| `db`            | SQLAlchemy async models, Alembic migrations |
| `notifications` | Email/Slack/webhook notification dispatch |
| `storage`       | Pluggable storage: LocalStorage ↔ S3Storage abstraction |
| `config`        | Pydantic settings: DB, storage, Deepgram, integrations |

### Agents (`temporalos/agents/`)
| Module        | Purpose |
|---------------|---------|
| `agents`      | Multi-agent orchestration, RAG agent, copilot agent |

### Integrations (`temporalos/integrations/`)
| Module          | Purpose |
|-----------------|---------|
| `integrations`  | Salesforce, HubSpot, Slack, Google Meet, Teams connectors |

### Enterprise (`temporalos/verticals/`, `enterprise/`, `batch/`, `clips/`, `webhooks/`)
| Module      | Purpose |
|-------------|---------|
| `verticals` | Industry packs (Sales, Support, HR, Legal) with custom extraction |
| `batch`     | Batch processing of multiple videos |
| `clips`     | Highlight clip generation from segments |
| `export`    | Export to CSV, PDF, Notion, Confluence |
| `webhooks`  | Outbound webhook dispatch on pipeline events |

### Fine-tuning (`temporalos/finetuning/`, `local/`)
| Module       | Purpose |
|--------------|---------|
| `finetuning` | LoRA fine-tuning on annotated segments (HuggingFace PEFT) |
| `local`      | Local SLM inference (Ollama, llama.cpp) for air-gapped deployments |

---

## API Routes

28 route modules under `temporalos/api/routes/`:

| Route            | Prefix                       | Description |
|------------------|------------------------------|-------------|
| `process`        | `/api/v1/process`            | Upload, status, results |
| `stream`         | `/api/v1/stream`             | WebSocket streaming pipeline |
| `search`         | `/api/v1/search`             | Semantic search |
| `intelligence`   | `/api/v1/intelligence`       | Objections, risk, intent analysis |
| `observatory`    | `/api/v1/observatory`        | Monitoring dashboard data |
| `metrics`        | `/api/v1/metrics`            | Prometheus-style metrics |
| `finetuning`     | `/api/v1/finetune`           | Training job management |
| `local`          | `/api/v1/local`              | Local SLM inference |
| `diarization`    | `/api/v1/diarization`        | Speaker diarization |
| `summaries`      | `/api/v1/summaries`          | Summarization |
| `clips`          | `/api/v1/clips`              | Clip generation |
| `export`         | `/api/v1/export`             | Data export |
| `batch`          | `/api/v1/batch`              | Batch processing |
| `schemas`        | `/api/v1/schemas`            | Schema management |
| `webhooks`       | `/api/v1/webhooks`           | Webhook configuration |
| `integrations`   | `/api/v1/integrations`       | CRM/Slack connectors |
| `agents`         | `/api/v1/agents`             | Agent orchestration |
| `notifications`  | `/api/v1/notifications`      | Notification management |
| `auth`           | `/api/v1/auth`               | Authentication & RBAC |
| `annotations`    | `/api/v1/annotations`        | Human annotation CRUD |
| `active_learning`| `/api/v1/active-learning`    | Review queue & gating |
| `audit`          | `/api/v1/audit`              | Audit trail |
| `diff`           | `/api/v1/diff`               | Call comparison |
| `patterns`       | `/api/v1/patterns`           | Pattern mining |
| `copilot`        | `/api/v1/copilot`            | Live coaching |
| `admin`          | `/api/v1/admin`              | Tenant/user/role admin |

Interactive API docs: `http://localhost:8000/docs` (Swagger UI) or `/redoc` (ReDoc).

---

## Frontend Pages

25 React pages at `frontend/src/pages/`:

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Overview with job stats |
| Upload | `/upload` | Video upload |
| Jobs | `/jobs` | Job list |
| JobDetail | `/jobs/:id` | Single job results |
| Search | `/search` | Semantic search |
| Intelligence | `/intelligence` | Objection/risk analysis |
| Observatory | `/observatory` | Drift & accuracy monitoring |
| FineTuning | `/finetuning` | Training job management |
| LocalSLM | `/local` | Local model inference |
| Streaming | `/streaming` | Live streaming pipeline |
| Vision | `/vision` | Visual analysis |
| Schemas | `/schemas` | Schema management |
| Clips | `/clips` | Clip generation |
| Export | `/export` | Data export |
| Batch | `/batch` | Batch processing |
| Integrations | `/integrations` | CRM connectors |
| Agents | `/agents` | Multi-agent orchestration |
| Annotations | `/annotations` | Human annotation |
| ReviewQueue | `/review` | Active learning queue |
| AuditLog | `/audit` | Audit trail |
| DiffView | `/diff` | Call comparison |
| PatternMiner | `/patterns` | Pattern mining |
| LiveCopilot | `/copilot` | Real-time coaching |
| Admin | `/admin` | System administration |
| Settings | `/settings` | User preferences |

---

## Data Flow

```
Video Upload → FFmpeg extraction → [Audio + Frames]
                                        │
                    ┌───────────────────┤
                    ▼                    ▼
              Whisper/Deepgram    Vision/OCR Analysis
              (transcript)        (slides, screens)
                    │                    │
                    └────────┬───────────┘
                             ▼
                    Temporal Alignment
                    (frame ↔ word sync)
                             │
                             ▼
                    Structured Extraction
                    (objections, intent,
                     risk, decisions)
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              Vector Index       PostgreSQL
              (search)           (structured data)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Pydantic |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Database | PostgreSQL 15 + Alembic migrations |
| ASR | Whisper (local), Deepgram (streaming) |
| Vision | GPT-4o / Claude Vision, Tesseract OCR |
| Search | Vector embeddings, semantic similarity |
| Fine-tuning | LoRA via HuggingFace PEFT |
| Observability | OpenTelemetry, Prometheus |
| CI/CD | GitHub Actions (lint, test, security scan) |
| Deployment | Docker Compose, Nginx reverse proxy |
