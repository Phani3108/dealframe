# DealFrame (formerly TemporalOS) — Project Rules & Context

## Project Overview
**DealFrame** is a Video → Structured Negotiation Intelligence Engine.
It converts video (sales calls, demos, walkthroughs) into machine-consumable structured intelligence — extracting segments with topics, sentiment, risk scores, objections, decision signals, and intent.

## Core Learning Goals
1. **Monitoring & Observability** — Production-grade telemetry, drift detection, accuracy tracking
2. **Real-time Multimodal Application** — Streaming ASR, vision, temporal alignment in real-time
3. **Fine-tuning Projects** — LoRA fine-tuning on annotated video segments for structured extraction

## Strict Project Rules

### 0. End-to-End Testing (MANDATORY — every phase)
- **After every phase is implemented, a full end-to-end test MUST be run and pass before moving on.**
- Every phase has a dedicated `tests/e2e/test_phase{N}_*.py` file.
- Tests must:
  - Generate a synthetic test video (FFmpeg, no external assets required)
  - Run the entire pipeline (all real code; only external API calls are mocked)
  - Assert the correct output schema and non-empty results
- `make test` runs unit tests. `make test-e2e` runs the full end-to-end suite.
- A phase is not "done" until `make test-e2e` passes with 0 failures.

### 1. Task Tracking (MANDATORY)
- Every user prompt and every task performed MUST be recorded in `tasks.md`
- Tasks must be checked off when completed
- This provides a complete audit trail of all work done on this project
- No exceptions — even exploratory or research tasks get logged

### 2. Planning Documentation
- `planning.md` must always be kept up to date with current architecture, decisions, and roadmap
- All architectural decisions must be documented with rationale
- Changes to the plan must be versioned with dates

### 3. File Structure Rules
- `claude.md` — This file. Project rules, context, conventions
- `tasks.md` — Complete task log with status tracking
- `planning.md` — Architecture, design decisions, roadmap

### 4. Code Conventions (to be expanded as project grows)
- Python as primary language
- Type hints everywhere
- Modular architecture — each system module is its own package
- Configuration via environment variables / YAML
- All ML pipelines must have evaluation metrics logged
- Observability built-in from day one, not bolted on

### 5. Git Conventions
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Feature branches off `main`
- PRs with description linking to tasks.md entries

## System Modules Reference
1. **Video Processing** — FFmpeg frame extraction, scene detection
2. **Vision + OCR** — Slide detection, UI screens, pricing tables
3. **Audio Pipeline** — Streaming ASR (Deepgram/Whisper), chunked transcripts
4. **Temporal Alignment** — Frame ↔ transcript synchronization at timestamp level
5. **Structured Extraction** — LoRA fine-tuned model for objections, intent, decision signals
6. **Observability** — Extraction accuracy, model drift detection, pipeline telemetry

## Tech Stack (Planned)
- **Video**: FFmpeg, OpenCV, PySceneDetect
- **Vision/OCR**: GPT-4o / Claude Vision / Qwen-VL, Tesseract/EasyOCR
- **ASR**: Deepgram (streaming), Whisper (local)
- **Fine-tuning**: LoRA via Hugging Face PEFT, Unsloth
- **Orchestration**: FastAPI, Celery/Temporal
- **Observability**: OpenTelemetry, Prometheus, Grafana, custom drift detectors
- **Eval**: DeepEval (already initialized), custom metrics
- **Storage**: PostgreSQL, S3-compatible (MinIO for local)
