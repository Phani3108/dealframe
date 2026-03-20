<div align="center">

# TemporalOS

**Video → Structured Decision Intelligence Engine**

*Convert sales calls, demos, and walkthroughs into machine-queryable intelligence*

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-208%20passing-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## What is TemporalOS?

Video is wasted data. A sales call contains timestamped objections, decision signals, pricing reactions, and competitive mentions — all buried in an unstructured mp4. TemporalOS extracts it into a structured, queryable intelligence graph.

**Input**: a sales call video  
**Output**:
```json
{
  "segments": [
    {
      "timestamp": "12:32",
      "topic": "pricing",
      "customer_sentiment": "hesitant",
      "risk": "high",
      "risk_score": 0.75,
      "objections": ["The price seems high compared to competitors"],
      "decision_signals": ["Can you send a proposal?"],
      "model": "gpt4o"
    }
  ],
  "overall_risk_score": 0.67
}
```

---

## Architecture

```
Video File
        │
   ┌────▼─────┐      ┌──────────────┐
   │  FFmpeg  │      │   Whisper    │
   │  Frames  │      │  Transcript  │
   └────┬─────┘      └──────┬───────┘
        │                   │
        └──────────┬─────────┘
                   │
          ┌────────▼────────┐
          │    Temporal     │
          │    Alignment    │   ← frame ↔ transcript fusion
          └────────┬────────┘
                   │
          ┌────────▼────────┐   ┌─────────────────────┐
          │   Extraction    │◄──│  Observatory        │ ← multi-model compare
          │  (GPT-4o/Claude │   │  (Phase 2)          │
          │  /Qwen / LoRA)  │   └─────────────────────┘
          └────────┬────────┘
                   │
     ┌─────────────┴──────────────┐
     │                            │
┌────▼──────────┐      ┌──────────▼──────────┐
│ Multi-video   │      │  Fine-tuning Arc     │
│ Intelligence  │      │  (Phase 4)           │
│ (Phase 3)     │      │  DatasetBuilder      │
│ Objections /  │      │  LoRATrainer         │
│ Risk Trends   │      │  ModelRegistry       │
└───────────────┘      └──────────────────────┘
                                  │
                       ┌──────────▼──────────┐
                       │  Local SLM Pipeline  │
                       │  (Phase 5)           │
                       │  Zero API calls      │
                       │  Rule-based fallback │
                       └─────────────────────┘

    ════════════════════════════════
    ║     Observability Layer      ║   ← OpenTelemetry spans on every stage
    ════════════════════════════════
```

---

## Core Learning Goals

This project is intentionally scoped around three deep skill areas:

| Goal | What We Build |
|------|--------------|
| **Monitoring & Observability** | OpenTelemetry on every pipeline stage, accuracy tracking, drift detection |
| **Real-time Multimodal** | Streaming ASR + live frame capture + incremental extraction |
| **Fine-tuning** | Full LoRA arc: dataset collection → training → eval → deploy |

---

## Project Phases

| Phase | Name | Status |
|-------|------|--------|
| **0** | Project Scaffold | ✅ Done |
| **1** | Walking Skeleton (FFmpeg + Whisper + GPT-4o) | ✅ Done |
| **2** | Comparative Model Observatory (GPT-4o vs Claude vs Qwen2.5-VL) | ✅ Done |
| **3** | Multi-video Intelligence (portfolio analytics) | ✅ Done |
| **4** | Fine-tuning Arc (LoRA dataset → training → eval → registry) | ✅ Done |
| **5** | Local SLM Pipeline (zero API calls + rule-based fallback) | ✅ Done |
| **6** | Frontend Dashboard (React + Vite + Tailwind SPA) | ✅ Done |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) (`brew install ffmpeg` on macOS)
- PostgreSQL (via Docker — included)
- OpenAI API key (for Phase 1/2 extraction)

### Setup

```bash
# Clone
git clone https://github.com/Phani3108/TemporalOS.git
cd TemporalOS

# Environment
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, optionally set AUDIO__WHISPER_MODEL=base for fast dev

# Install
pip install -e ".[audio,dev]"

# Start Postgres
make db-up

# Start API
make dev
# → http://localhost:8000
# → http://localhost:8000/docs
```

### Process a video

```bash
# Via Makefile
make process VIDEO=my_call.mp4

# Or directly
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@my_call.mp4"
# → {"job_id": "abc-123", "status": "pending"}

curl http://localhost:8000/api/v1/jobs/abc-123
# → {"status": "completed", "result": {...}}
```

---

## Testing

End-to-end tests are **mandatory** after every phase (see [claude.md](claude.md) §0).  
Tests generate synthetic videos via FFmpeg — no external assets required.  
External API calls are mocked.

```bash
# Unit tests (fast)
make test
# → 47 passed

# End-to-end tests (tests the full pipeline)
make test-e2e
# → 161+ passed

# All tests
make test-all
```

**Current test status**: `208 passed, 0 failed`

---

## Project Structure

```
TemporalOS/
├── temporalos/
│   ├── api/
│   │   └── routes/     # process, observatory, intelligence, finetuning, local
│   ├── alignment/      # Temporal frame↔transcript fusion
│   ├── audio/          # Whisper batch transcription
│   ├── core/           # Shared types (Frame, Word, AlignedSegment, ExtractionResult)
│   ├── db/             # SQLAlchemy models + async session
│   ├── extraction/
│   │   └── models/     # GPT-4o, Claude, FineTunedExtractionModel adapters
│   ├── finetuning/     # DatasetBuilder, LoRATrainer, ExtractionEvaluator, ModelRegistry
│   ├── ingestion/      # FFmpeg frame extraction
│   ├── intelligence/   # Multi-video aggregation (Phase 3)
│   ├── local/          # LocalPipeline, _RuleBasedExtractor, BenchmarkRunner (Phase 5)
│   ├── observatory/    # ObservatoryRunner + Comparator (Phase 2)
│   ├── observability/  # OpenTelemetry telemetry singleton
│   └── vision/         # BaseVisionModel + GPT-4o / Claude / Qwen2.5-VL adapters
├── tests/
│   ├── conftest.py     # Shared fixtures (synthetic test video, sample data)
│   ├── unit/           # 47 unit tests per module
│   └── e2e/            # 130 end-to-end tests — one file per phase
├── evals/
│   └── extraction_eval.py  # DeepEval metrics + schema_pass_rate()
├── config/
│   └── settings.yaml   # Default configuration
├── claude.md           # Project rules & conventions (read this first)
├── planning.md         # Architecture, decisions, phased roadmap
├── frontend/
│   ├── src/
│   │   ├── api/        # Typed API client (all 5 route groups)
│   │   ├── components/ # Layout, StatCard, Badge, SegmentCard
│   │   └── pages/      # Dashboard, Upload, Results, Observatory, Intelligence, Finetuning, LocalPipeline
│   ├── dist/           # Built SPA (served by FastAPI at /)
│   ├── package.json    # React 18 + Vite 5 + Tailwind 3 + recharts + lucide-react
│   └── vite.config.ts  # Proxy /api → localhost:8000 in dev
├── tasks.md            # Complete task audit log
├── Makefile            # dev / test / test-e2e / process / db-up / frontend-*
├── docker-compose.yml  # PostgreSQL service
└── pyproject.toml      # Dependencies (core, audio, vision, finetuning, dev)
```

---

## Configuration

All settings live in `config/settings.yaml` and can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (required for gpt4o mode) |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (Claude adapters) |
| `TEMPORALOS_MODE` | `api` | `api` (cloud models) or `local` (offline, Phase 5) |
| `AUDIO__WHISPER_MODEL` | `large-v3` | Whisper model size (`base` for fast dev) |
| `VIDEO__FRAME_INTERVAL_SECONDS` | `2` | Frame extraction frequency |
| `DATABASE_URL` | postgres://... | PostgreSQL connection string |
| `FINETUNING__BASE_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.3` | HuggingFace model for LoRA training |
| `FINETUNING__ADAPTER_PATH` | `""` | Path to fine-tuned LoRA adapter (empty = rule-based fallback) |
| `FINETUNING__DATASET_DIR` | `/tmp/temporalos/finetuning/datasets` | Directory for training JSONL files |
| `FINETUNING__LORA_R` | `8` | LoRA rank |
| `FINETUNING__EPOCHS` | `3` | Training epochs |

---

## Observability

Every pipeline stage emits OpenTelemetry spans:

```
pipeline.run
  ├── ingestion.extract_frames    (duration, frame_count)
  ├── audio.transcribe            (duration, word_count, model)
  ├── alignment.align             (frame_count, non_empty_segments)
  └── extraction.gpt4o            (duration, latency_ms, timestamp_ms)
```

Set `TELEMETRY__OTLP_ENDPOINT=http://localhost:4317` to send traces to any OTEL-compatible backend (Jaeger, Grafana Tempo, etc.). Defaults to console output in development.

---

## API Reference

All routes are prefixed with `/api/v1`. Full OpenAPI docs at `http://localhost:8000/docs`.

### Core Pipeline (Phase 1)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/process` | Upload video → returns `job_id` (202) |
| `GET` | `/jobs/{job_id}` | Poll job status + result |
| `GET` | `/health` | Health check |

### Model Observatory (Phase 2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/observatory/compare` | Run video through all registered models (202) |
| `GET` | `/observatory/sessions/{id}` | Poll comparison session |
| `GET` | `/observatory/sessions` | List all comparison sessions |

### Video Intelligence (Phase 3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/intelligence/objections` | Top objections across all videos |
| `GET` | `/intelligence/topics/trend` | Topic frequency trend over time |
| `GET` | `/intelligence/risk/summary` | Risk score distribution |
| `POST` | `/intelligence/portfolios` | Create a video portfolio |
| `POST` | `/intelligence/portfolios/{id}/videos` | Add video to portfolio |

### Fine-tuning Arc (Phase 4)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/finetuning/dataset/export` | Build training JSONL from DB extractions (202) |
| `GET` | `/finetuning/dataset/stats` | Dataset size + class distribution |
| `POST` | `/finetuning/train` | Launch LoRA training job (202) |
| `GET` | `/finetuning/runs` | List training experiments |
| `GET` | `/finetuning/runs/{id}` | Get experiment status + metrics |
| `POST` | `/finetuning/runs/{id}/eval` | Evaluate adapter on validation set |
| `POST` | `/finetuning/runs/{id}/activate` | Set adapter as active extraction model |
| `GET` | `/finetuning/runs/{id}/calibration` | Get confidence calibration curve |
| `GET` | `/finetuning/best` | Get best experiment by metric |

### Local Pipeline (Phase 5)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/local/status` | Check which local models are available |
| `POST` | `/local/process` | Process video with zero API calls (202) |
| `GET` | `/local/process/{job_id}` | Poll local processing job |
| `GET` | `/local/jobs` | List all local processing jobs |
| `POST` | `/local/benchmark` | Run local vs API latency comparison |
### Frontend (Phase 6)

The compiled React SPA is served directly by FastAPI:

| Path | Description |
|------|-------------|
| `/` | Dashboard — stat cards, recent jobs, top objections |
| `/upload` | Upload & Process — drag-drop, stage tracker, mode selector |
| `/results/:jobId` | Analysis results — segment cards with risk-colored borders |
| `/observatory` | Multi-model comparison sessions |
| `/intelligence` | Cross-video analytics with Recharts charts |
| `/finetuning` | LoRA training lifecycle — runs table, activate model |
| `/local` | Local pipeline — model status, process locally |
| `/assets/*` | Static CSS/JS bundles (Vite build output) |
---

## Fine-tuning Workflow

```bash
# Step 1 — Build training dataset from high-confidence extractions
curl -X POST "http://localhost:8000/api/v1/finetuning/dataset/export?min_confidence=0.8"

# Step 2 — Check dataset stats
curl http://localhost:8000/api/v1/finetuning/dataset/stats

# Step 3 — Launch training (dry_run=true for testing)
curl -X POST "http://localhost:8000/api/v1/finetuning/train?name=v1&train_path=...&val_path=...&dry_run=false"
# → {"experiment_id": "abc-123", "status": "running"}

# Step 4 — Poll training progress
curl http://localhost:8000/api/v1/finetuning/runs/abc-123

# Step 5 — Activate the best adapter
curl -X POST http://localhost:8000/api/v1/finetuning/runs/abc-123/activate
# Sets FINETUNING__ADAPTER_PATH in settings. Future /local/process calls use this adapter.
```

---

## Local Pipeline (Zero API Calls)

```bash
# Check what's available locally
curl http://localhost:8000/api/v1/local/status
# → {"whisper_available": true, "finetuned_adapter_available": false, "active_extractor": "rule_based", "cost_per_video_usd": 0.0}

# Process a video with no external API calls
curl -X POST http://localhost:8000/api/v1/local/process \
  -F "file=@my_call.mp4"
# → {"job_id": "xyz-789", "status": "pending"}

# Run a cost/latency benchmark
curl -X POST http://localhost:8000/api/v1/local/benchmark \
  -F "file=@my_call.mp4"
# → {"latency_ratio": 1.3, "verdict": "local_recommended", "cost_savings_usd": 0.024}
```

The local pipeline falls back gracefully:
- **Fine-tuned adapter present** → uses `FineTunedExtractionModel` (LoRA adapter via PEFT)
- **No adapter** → uses `_RuleBasedExtractor` (keyword matching, zero dependencies, confidence=0.4)

---

## Frontend Dashboard (Phase 6)

The dashboard is a React 18 + Vite SPA with Tailwind CSS (white background, indigo primary, risk colour-coding).

### Development

```bash
# 1. Install frontend deps (one-time)
make frontend-install        # or: cd frontend && npm install

# 2. Build for production (served by FastAPI at localhost:8000)
make frontend-build          # → frontend/dist/

# 3. Start the API
make dev                     # FastAPI at http://localhost:8000
# Visit http://localhost:8000 to see the dashboard
```

### Hot-reload dev mode (optional)

```bash
# Terminal 1 — API backend
make dev                     # http://localhost:8000

# Terminal 2 — Vite dev server with hot-reload
make frontend-dev            # http://localhost:3000  (proxies /api → localhost:8000)
```

### Pages

| Route | Page |
|-------|------|
| `/` | **Dashboard** — stat cards, recent jobs table, top objections mini-chart |
| `/upload` | **Upload** — drag-drop zone, API/Local mode selector, live stage progress |
| `/results/:id` | **Results** — risk score, expandable segment cards (risk-coloured borders) |
| `/observatory` | **Observatory** — multi-model comparison, agreement scores |
| `/intelligence` | **Intelligence** — bar/pie/line charts via Recharts |
| `/finetuning` | **Fine-tuning** — training runs table, activate model button |
| `/local` | **Local Pipeline** — model status checks, process locally, job history |

---

## Key Files

- [claude.md](claude.md) — Project rules, conventions, strict requirements (read first)
- [planning.md](planning.md) — Full architecture, design decisions, decision log
- [tasks.md](tasks.md) — Complete audit trail of every task and prompt

---

## License

MIT
