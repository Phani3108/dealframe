# DealFrame — Planning & Architecture

> Last updated: 2026-03-26

> **See [EXPANSION.md](./EXPANSION.md) for the full expansion vision — industries, integrations, user tiers, and the 5-phase build plan.**

---

## 1. Vision Statement

Transform raw video into structured, queryable negotiation intelligence. A sales call isn't just audio — it's a timestamped graph of intent, objection, sentiment, and visual context. DealFrame makes that graph machine-consumable.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│  Video File (.mp4/.webm) OR Live Stream (RTMP/WebRTC)          │
└──────────────┬──────────────────────────────────┬───────────────┘
               │                                  │
       ┌───────▼────────┐                ┌────────▼───────┐
       │ VIDEO PIPELINE  │                │ AUDIO PIPELINE │
       │                 │                │                │
       │ • Frame extract │                │ • Deepgram     │
       │   (FFmpeg)      │                │   streaming    │
       │ • Scene detect  │                │ • Whisper      │
       │ • Keyframe      │                │   (local/batch)│
       │   selection     │                │ • Diarization  │
       └───────┬─────────┘                └────────┬───────┘
               │                                   │
       ┌───────▼─────────┐                ┌────────▼───────┐
       │ VISION ANALYSIS  │                │ TRANSCRIPT     │
       │                  │                │ PROCESSOR      │
       │ • Slide detect   │                │                │
       │ • OCR extraction │                │ • Chunking     │
       │ • UI recognition │                │ • Speaker ID   │
       │ • Chart/table    │                │ • Sentence     │
       │   parsing        │                │   boundaries   │
       └───────┬──────────┘                └────────┬───────┘
               │                                    │
               └──────────────┬─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │ TEMPORAL ALIGNMENT   │
                   │                      │
                   │ • Frame ↔ Transcript │
                   │ • Multimodal fusion  │
                   │ • Timeline graph     │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼──────────┐
                   │ STRUCTURED           │
                   │ EXTRACTION           │
                   │                      │
                   │ • LoRA fine-tuned    │
                   │   model              │
                   │ • Prompt-based       │
                   │   (zero-shot backup) │
                   │ • Schema validation  │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼──────────┐
                   │ OUTPUT / API         │
                   │                      │
                   │ • Structured JSON    │
                   │ • Dashboard          │
                   │ • Webhooks           │
                   │ • Search index       │
                   └─────────────────────┘

              ═══════════════════════════════
              ║    OBSERVABILITY LAYER      ║
              ║                             ║
              ║ • OpenTelemetry traces      ║
              ║ • Pipeline latency metrics  ║
              ║ • Extraction accuracy       ║
              ║ • Model drift detection     ║
              ║ • Cost tracking (API calls) ║
              ═══════════════════════════════
```

---

## 3. Module Deep Dive

### 3.1 Video Processing Module
**Purpose**: Extract analyzable frames from video input

| Component | Tool | Notes |
|-----------|------|-------|
| Frame extraction | FFmpeg | Extract every N seconds OR on scene change |
| Scene detection | PySceneDetect | Content-aware cuts, threshold-based |
| Keyframe selection | Custom | Reduce redundant frames (similarity hash) |
| Format handling | FFmpeg | Support mp4, webm, mkv, mov |

**Key decisions**:
- Fixed-interval vs adaptive frame extraction? → Start with fixed (1 frame/2sec), add adaptive later
- Resolution for vision models? → Resize to 1024px max dimension to balance quality/cost

### 3.2 Vision + OCR Module
**Purpose**: Extract visual information from frames

| Component | Approach | Notes |
|-----------|----------|-------|
| Slide detection | Classification model or heuristic | Detect presentation slides vs face vs screen |
| OCR | EasyOCR (local) / GPT-4o vision | Structured text extraction |
| UI recognition | Vision LLM | Identify software interfaces, forms |
| Chart/table parsing | Vision LLM + custom | Extract data from visible charts |

**Expansion opportunity**: 
- Compare GPT-4o vs Claude Vision vs Qwen2.5-VL vs LLaVA for accuracy/cost
- Build a **vision model benchmark** specific to sales/demo video content
- Table structure recognition is a hard sub-problem worth isolating

### 3.3 Audio Pipeline Module
**Purpose**: Convert speech to timestamped text

| Component | Tool | Notes |
|-----------|------|-------|
| Batch ASR | Whisper (local) | whisper-large-v3, insanely-fast-whisper |
| Streaming ASR | Deepgram Nova-2 | Real-time with word-level timestamps |
| Speaker diarization | pyannote-audio | Who said what |
| Language detection | Whisper built-in | Multi-language support |

**Key decisions**:
- Streaming vs batch? → Support both. Batch for uploaded files, streaming for live
- Word-level vs sentence-level timestamps? → Word-level, aggregate to sentences

### 3.4 Temporal Alignment Module (THE HARD PART)
**Purpose**: Fuse visual and audio streams into a unified timeline

This is the core differentiator. At any timestamp `t`, you need:
```
{
  "t": "12:32",
  "frame": { "type": "slide", "ocr_text": "Enterprise Plan: $499/mo", "objects": [...] },
  "transcript": { "speaker": "sales_rep", "text": "So this is our enterprise tier..." },
  "audio_features": { "pace": "slow", "confidence": 0.8 }
}
```

**Alignment strategies**:
1. **Timestamp-based join** (simple) — nearest-neighbor match of frame timestamps to transcript word timestamps
2. **Cross-modal attention** (advanced) — model learns to attend across modalities
3. **Event-based anchor points** — use slide transitions or speaker changes as alignment anchors

**Start with #1, evolve to #3, research #2.**

### 3.5 Structured Extraction Module (FINE-TUNING FOCUS)
**Purpose**: Extract business intelligence from aligned multimodal segments

**What to extract**:
- Objections ("That's too expensive", "We're already using X")
- Decision signals ("Let me bring in my manager", "Can you send a proposal?")
- Sentiment per segment (positive/neutral/negative/hesitant)
- Topics (pricing, features, competition, timeline, security)
- Risk indicators (ghosting risk, champion loss, competitor mention)
- Action items mentioned

**Fine-tuning approach**:
1. **Phase 1**: Prompt engineering with GPT-4o / Claude — establish baseline
2. **Phase 2**: Collect annotations, build dataset (100-500 examples)
3. **Phase 3**: LoRA fine-tune Mistral-7B or Llama-3-8B using PEFT
4. **Phase 4**: Distill to smaller model for production (Phi-3, Qwen2.5-3B)

**Dataset structure**:
```json
{
  "input": "<aligned_segment with visual + transcript context>",
  "output": {
    "topic": "pricing",
    "sentiment": "hesitant",
    "objections": ["Price is higher than competitor"],
    "decision_signals": [],
    "risk_level": "high"
  }
}
```

### 3.6 Observability Module
**Purpose**: Production-grade monitoring of the entire pipeline

| Metric | Type | Tool |
|--------|------|------|
| Pipeline latency (per stage) | Histogram | OpenTelemetry + Prometheus |
| ASR word error rate | Gauge | Custom eval against ground truth |
| Extraction accuracy (precision/recall) | Gauge | DeepEval + custom |
| Model confidence distribution | Histogram | Custom |
| Drift detection | Alert | Evidently AI / custom |
| API cost per video | Counter | Custom middleware |
| Frame processing throughput | Counter | OpenTelemetry |
| Queue depth (async pipeline) | Gauge | Celery/Temporal metrics |

**Key observability features to build**:
- **Confidence calibration** — is model's 0.8 confidence actually 80% accurate?
- **Drift detection** — statistical tests on extraction distribution over time
- **Human-in-the-loop feedback** — flag low-confidence extractions for review
- **A/B comparison** — run two models side-by-side, compare outputs

---

## 4. Phased Roadmap

### ✅ Phase 1: Foundation — DONE
- [x] Project scaffolding, config, CI
- [x] FFmpeg frame extraction, scene detection, keyframe deduplication
- [x] Whisper batch ASR, streaming ASR (WebSocket)
- [x] Temporal alignment
- [x] GPT-4o + Claude extraction models
- [x] FastAPI: upload → job poll → results
- [x] OpenTelemetry + Prometheus metrics

### ✅ Phase 2: Observatory & Multi-Video Intelligence — DONE
- [x] Comparative model observatory (GPT-4o vs Claude vs Qwen-VL)
- [x] Pairwise agreement scoring
- [x] Multi-video aggregation (objections, topic trends, risk summary)
- [x] Portfolio view

### ✅ Phase 3: Vision & OCR — DONE
- [x] Scene detection, keyframe selection
- [x] EasyOCR pipeline, slide classifier (SLIDE/FACE/CHART/SCREEN)
- [x] Vision pipeline (Qwen-VL, GPT-4o Vision, Claude Vision)

### ✅ Phase 4: Fine-tuning Arc — DONE
- [x] Dataset builder (JSONL export for LoRA)
- [x] LoRA trainer (PEFT, dry-run mode for CI)
- [x] Evaluator (field-level accuracy, F1, calibration curve)
- [x] Model registry (JSON-backed versioning)
- [x] Fine-tuned extraction model adapter

### ✅ Phase 5: Local SLM Pipeline — DONE
- [x] Rule-based extractor (zero dependencies)
- [x] LocalPipeline (Whisper + rule-based + optional Qwen-VL)
- [x] Benchmark runner (local vs API cost/latency)

### ✅ Phase 6: Frontend Dashboard — DONE
- [x] React 18 + Vite + Tailwind SPA
- [x] 10 pages, full design system
- [x] Dashboard, Upload, Results, Observatory, Intelligence, Fine-tuning, Local Pipeline, Observability, Search, Streaming

### ✅ Phase 7: Observability & Drift Detection — DONE
- [x] Drift detector (Welch's t-test, KL divergence)
- [x] Confidence calibration (ECE, reliability bins)
- [x] Review queue, human-in-the-loop labeling
- [x] Prometheus metrics endpoint

### ✅ Phase 8: Streaming Pipeline — DONE
- [x] MockStreamingASR (byte-rate model)
- [x] StreamingPipeline (async generator, chunked extraction)
- [x] WebSocket endpoint (/ws/stream)

### ✅ Phase 9: Scene Intelligence — DONE
- [x] SceneDetector, KeyframeSelector, VisionPipeline
- [x] EnrichedFrame with OCR + classification

### ✅ Phase 10: Search & Portfolio Insights — DONE
- [x] TF-IDF SearchIndex (inverted index, risk/topic filter)
- [x] Portfolio insights: win/loss patterns, objection velocity, rep comparison

---

### ✅ Phase A: Platform Primitives — DONE
- [x] A1 — Speaker diarization (heuristic-based, pyannote stub)
- [x] A2 — Auto-summary engine (8 template types, rule-based)
- [x] A3 — Clip extractor API (FFmpeg cut + serve)
- [x] A4 — Custom schema builder (YAML → extraction prompt)
- [x] A5 — Webhook delivery system (HMAC-SHA256, retry)
- [x] A6 — Python SDK (stdlib-only, zero deps)

### ✅ Phase B: Integrations — DONE
- [x] B1 — Zoom webhook helpers + signature verification
- [x] B3 — Slack Block Kit builders + command routing
- [x] B5 — Salesforce OAuth2 + Task creation
- [x] B6 — HubSpot enrichment helpers
- [x] B8 — LangChain tool adapter
- [x] B9 — LlamaIndex reader adapter

### ✅ Phase C: Intelligence Layer — DONE
- [x] C1 — Q&A agent (TF-IDF retrieval, rule-based synthesis)
- [x] C2 — Risk agent (threshold/spike/persist alerts)
- [x] C3 — Coaching engine (5-dimension scoring + grades)
- [x] C4 — Knowledge graph (keyword entity extraction, NetworkX)
- [x] C5 — Meeting prep agent (risk trajectory, talking points)

### ✅ Phase D: Vertical Packs — DONE (schema stubs)
- [x] Sales Pack (schema definition, 12 fields)
- [x] UX Research Pack (schema definition, 12 fields)
- [x] Customer Success Pack (schema definition)
- [x] Real Estate Pack (schema definition)

---

## ⚡ HONEST ASSESSMENT (2026-03-21)

**Phases A–D delivered structure, not intelligence.** All extraction, synthesis, and agents
are keyword/rule-based. No LLM is actually wired in. All state is in-memory with no
persistence. Frontend pages render but show empty states. Integrations are helpers, not
working OAuth flows. Verticals are schemas-only with no processors.

**To reach top 1%, the next 4 phases must deliver real AI, real workflows, real uniqueness,
and real enterprise readiness — in that order.**

---

### ✅ Phase E: AI-Native Core — COMPLETE (27 tests passing)
*Wire real AI into every critical path. Replace rule-based with LLM-powered.*

| # | Component | What it does |
|---|-----------|-------------|
| E1 | **LLM Extraction Router** | Replace rule-based extractors with actual LLM calls. `ExtractionRouter` picks GPT-4o / Claude / local Ollama based on config + budget. Structured JSON output via Pydantic, retry + validation. Graceful fallback to rule-based on failure. |
| E2 | **AI-Powered Summarization** | Wire LLM into all 8 summary templates. Prompt templates per type → LLM call → stream response → cache in DB. Support streaming UI. |
| E3 | **Semantic Vector Store** | Replace TF-IDF with real embeddings (OpenAI `text-embedding-3-small` or local `all-MiniLM-L6-v2`). Persist to SQLite + `sqlite-vec` for zero-dependency local dev. ChromaDB as optional upgrade. |
| E4 | **RAG-Powered Q&A Agent** | Real retrieval-augmented generation: embed → retrieve → LLM synthesize → cite with exact video timestamps. Context window management for large libraries. |
| E5 | **Smart Coaching with LLM** | After 5-dimension scoring, LLM generates natural-language coaching narrative. Cites specific call moments. Compares to team benchmarks with actionable advice. |
| E6 | **NER-Based Knowledge Graph** | Replace keyword extraction with spaCy NER or LLM-based entity extraction. Persist nodes/edges to DB. Enable graph queries: "What do we know about Acme Corp?" |
| E7 | **Meeting Prep with Context** | LLM generates prep brief pulling from: past calls with same company, CRM context, risk trajectory. Structured output: talking points, watch-outs, recommended approach. |
| E8 | **Persistent State Layer** | Move ALL in-memory state to DB: risk events, KG nodes/edges, embeddings, summary cache, coaching history, batch jobs. New SQLAlchemy models + Alembic migrations. |
| E9 | **pyannote Speaker Diarization** | Wire real pyannote-audio (with heuristic fallback). Persist speaker labels per segment. Manual speaker labeling: "Speaker A = John Smith". |

**Frontend changes:**
- Chat: real AI responses with streaming text + source citations
- Coaching: LLM-generated narrative, highlighted call moments
- Knowledge Graph: interactive D3.js/Cytoscape visualization
- Meeting Prep: structured brief card with risk chart + talking points
- Results: AI-generated summary panel with template selector + streaming

**Tests:** `test_phase_e_ai_core.py` — mocked LLM responses, real pipeline flows, persistence verification.

---

### ✅ Phase F: Real-World Workflows — COMPLETE (25 tests passing)
*Make it actually usable. Demo data. Auth. Polished UX. Working integrations.*

| # | Component | What it does |
|---|-----------|-------------|
| F1 | **Demo Seed Generator** | Script to create 15-20 realistic demo entries: 5 companies, 8 reps, 60 calls. Dashboard, coaching, risk alerts, KG all populated on first boot. |
| F2 | **Onboarding Wizard** | First-run flow: "Upload your first video" → "See analysis" → "Try Q&A" → "Set up alerts". Progress persisted in localStorage. Empty state CTAs everywhere. |
| F3 | **Authentication System** | JWT auth: register/login/refresh. API keys for SDK access. Rate limiting per tier (free: 3 videos/month, pro: unlimited). Password hashing via bcrypt. |
| F4 | **Dashboard 2.0** | Real-time metrics: videos processed, avg risk this week, top objections. Activity feed. Risk heatmap calendar. Responsive grid layout. |
| F5 | **Results 2.0** | Tabbed view: Transcript (speaker-colored, scrollable synced to video) → Extraction → Summary → Clips → Speakers → Timeline. Embedded HTML5 video player. |
| F6 | **Analytics 2.0** | Full Recharts dashboard: date range picker, objection trends, risk distribution, rep leaderboard, topic heatmap. CSV/PDF export. |
| F7 | **Working Zoom OAuth** | Full flow: "Connect Zoom" → OAuth2 authorize → receive recording webhooks → auto-download + process. Status shown in Integrations page. |
| F8 | **Working Slack OAuth** | Install flow → slash commands (`/tos search`, `/tos risk`) → daily digest cron → Block Kit rich messages with call links. |
| F9 | **Export Engine** | One-click export: PDF report (branded template), Markdown, JSON, CSV. Summary + extraction + speakers in a single downloadable artifact. |
| F10 | **Notification System** | In-app notification bell + email alerts (SMTP/SendGrid): high-risk call, batch complete, model drift, weekly digest. User preferences UI. |

**Frontend component library:**
- `<DataTable>` — sortable, filterable, paginated
- `<EmptyState>` — with CTA buttons per page context
- `<Timeline>` — horizontal video segment timeline
- `<PlayerSync>` — HTML5 video + synced transcript scroller
- `<Chart>` — Recharts wrapper with consistent styling
- Dark mode toggle in Layout

**Tests:** `test_phase_f_workflows.py` — auth flow, demo seed, export generation, Zoom/Slack OAuth mocks.

---

### ✅ Phase G: Competitive Moats — COMPLETE (41 tests passing)
*Features no competitor has. This is what makes DealFrame top 1%.*

| # | Component | What it does | Why it's unique |
|---|-----------|-------------|----------------|
| G1 | **Temporal Diff Engine** | Compare two calls with the same company. Semantic diff: new objections, resolved concerns, risk trajectory, topic evolution. Visual side-by-side. | **Nobody has call-to-call semantic diff.** Gong tracks keywords over time but can't show "what changed between call 3 and call 4 with Acme." |
| G2 | **Franchise Mode** | Auto-detect vertical from content (sales call? UX interview? legal deposition?) and apply the right schema automatically. One instance, multiple verticals. | **Nobody auto-classifies and adapts.** Gong=sales-only. Dovetail=UX-only. DealFrame adapts to any content. |
| G3 | **Cross-Call Pattern Mining** | Statistical patterns across library: "Calls mentioning competitor X close 30% less" or "Reps asking 5+ questions have 2x win rate." Automated insight generation. | **Nobody does causal pattern mining.** Current tools show counts; this finds correlations that change behavior. |
| G4 | **Live Call Copilot** | During live call (WebSocket stream), surface real-time coaching: "Prospect mentioned competitor — here's your battlecard" or "Risk rising — ask about timeline." Overlay UI. | **Real-time AI coaching during the call.** Gong does post-call only. This changes the outcome while it's happening. |
| G5 | **Visual Intelligence** | When prospect shares screen, extract structured data from visual frames: pricing pages, competitor dashboards, org charts. "Prospect was viewing Competitor X at $299/mo." | **Nobody extracts intel from shared screen content.** Turns screen-share into competitive intelligence. |
| G6 | **Collaborative Annotations** | Team members highlight transcript segments, add comments, tag with labels. Labels feed into fine-tuning dataset. Threaded discussions on specific moments. | **Human-in-the-loop that improves the model.** Every annotation makes extraction better over time. |
| G7 | **Smart Clip Reels** | Auto-generate highlight reels: "Best objection handles this week," "All competitor mentions in March." Compiled into single video with transitions. | **Nobody auto-generates curated video compilations** from call libraries. |
| G8 | **Confidence-Gated Active Learning** | Low-confidence extractions route to human review queue. Reviewed labels added to training set. Over time, model improves on exactly the segments it struggles with. | **Active learning loop.** The product literally gets smarter from usage. |

**Frontend:**
- `DiffView.tsx` — side-by-side call comparison with highlighted changes
- `LiveCopilot.tsx` — real-time prompts overlay during WebSocket stream
- `Annotations.tsx` — inline transcript annotations with reply threads
- `ClipReel.tsx` — drag-and-drop reel builder
- `PatternMiner.tsx` — statistical insights with correlation cards

**Tests:** `test_phase_g_moats.py` — diff engine, pattern mining, copilot mock, annotation CRUD.

---

### ✅ Phase H: Enterprise Scale & Polish — COMPLETE (53 tests passing)

### ✅ Phase I: State Persistence & Data Integrity — COMPLETE (40 tests passing)

### ✅ Phase J: Frontend Completion & Real UX — COMPLETE (36 tests passing)
*Every backend module gets an API route. Every route gets a frontend page.*

| # | Component | What it does |
|---|-----------|-------------|
| J1 | **7 API Route Files** | annotations, active_learning, audit, diff, patterns, copilot, admin — full CRUD/query routes |
| J2 | **API Client Expansion** | ~200 lines of typed functions in client.ts for all new endpoints |
| J3 | **8 New React Pages** | Annotations, ReviewQueue, AuditLog, DiffView, PatternMiner, LiveCopilot, Admin, SettingsPage |
| J4 | **Navigation & Layout** | 8 new nav items, notification bell with dropdown, updated App.tsx routes |

### ✅ Phase K: Real Integrations & Production Streaming — COMPLETE (31 tests passing)
*Replace stubs with real implementations. Production-grade streaming and storage.*

| # | Component | What it does |
|---|-----------|-------------|
| K1 | **Deepgram WebSocket ASR** | Real streaming transcription via Deepgram WebSocket SDK, word-level timestamps |
| K2 | **Storage Abstraction** | StorageBackend ABC → LocalStorage (filesystem, path traversal protection) + S3Storage (boto3) |
| K3 | **Config Consolidation** | StorageSettings, DeepgramSettings, IntegrationSettings in Pydantic settings |

### ✅ Phase L: CI/CD, Security & Production Hardening — COMPLETE (18 tests passing)
*Automated quality gates, security hardening, health probes.*

| # | Component | What it does |
|---|-----------|-------------|
| L1 | **GitHub Actions CI** | 4 jobs: lint (ruff+mypy), test-backend (pytest+coverage), test-frontend (tsc), security (bandit) |
| L2 | **Security Headers** | 8 headers on every response: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, etc. |
| L3 | **Health Probes** | /health/live (liveness), /health/ready (readiness + DB check) |
| L4 | **Docker Compose** | 3 services (postgres, app, frontend) with health checks and named volumes |

### ✅ Phase M: Documentation, SDK & Developer Experience — COMPLETE (27 tests passing)
*Make the project accessible, documented, and SDK-ready.*

| # | Component | What it does |
|---|-----------|-------------|
| M1 | **Python SDK** | Zero-dependency DealFrameClient with 13 typed methods, dataclass results, error handling |
| M2 | **Deployment Guide** | Docker, env vars, local dev, production (Nginx, probes), storage, monitoring |
| M3 | **Architecture Docs** | System diagram, module map, all 28 routes, 25 pages, data flow, tech stack |
| M4 | **API Reference** | All endpoints with request/response examples, auth guide, SDK usage |
| M5 | **README** | Updated with Docker quickstart, SDK section, doc links, 688+ test count |
*Fix the "everything in-memory" problem. Data survives restarts. Alembic migrations.*

| # | Component | What it does |
|---|-----------|-------------|
| I1 | **Alembic Migrations** | Async template, 3 migrations (initial schema, annotations+review_items, user tier). `alembic upgrade head` applies all. |
| I2 | **AnnotationRecord + ReviewItemRecord** | New DB models for annotations (uid, job_id, label, tags, resolved) and review queue (uid, confidence, status, corrected_extraction). |
| I3 | **AuditTrail → DB** | async_log(), async_query(), load_from_db(). Write-through pattern: sync in-memory + async DB persist. |
| I4 | **NotificationService → DB** | async_send(), async_mark_read(), load_from_db(). Notifications survive restart. |
| I5 | **AnnotationStore → DB** | async_create/update/delete(), load_from_db(). All CRUD persisted. |
| I6 | **ActiveLearningQueue → DB** | async_gate/approve/correct/reject(), load_from_db(). Review queue state persisted. |
| I7 | **Auth → DB** | Stable AUTH_SECRET from env var. persist_user(), load_users_from_db(). Tokens survive restart. |
| I8 | **Multi-Tenant → DB** | async_register_tenant(), load_tenants_from_db(). Tenant registry persisted. |
| I9 | **App Startup Wiring** | lifespan init → get_session_factory → init all services → load_from_db for each. |

**Architecture Pattern:** Write-through cache. Each service has:
- `_sf`: Optional async session_factory (None = in-memory only, provided = DB persistence)
- Sync methods: unchanged (backward compat, used by tests)
- `async_*` methods: sync write + DB persist (used by production routes)
- `load_from_db()`: populate in-memory cache at startup

**Tests:** `test_phase_i_persistence.py` — 40 tests covering round-trips for all services.
*Production-grade for enterprise deployment. Security, scale, compliance.*

| # | Component | What it does |
|---|-----------|-------------|
| H1 | **Multi-Tenant Architecture** | Row-level tenant isolation. Middleware injects `tenant_id` into every query. Separate storage paths. |
| H2 | **SSO / OAuth2 Providers** | Login with Google, Microsoft (Azure AD), Okta SAML. Map groups to roles. |
| H3 | **Role-Based Access Control** | Roles: Admin, Manager, Analyst, Viewer. Field-level permissions on extraction data. Managers see all reps; Viewers see summaries only. |
| H4 | **Persistent Task Queue** | Celery + Redis (or Temporal) replaces in-memory threading. Priority lanes, dead letter queue, retry policies. |
| H5 | **PII Redaction Engine** | Redact names, phones, emails, SSNs, credit cards before storage. Uses presidio. Configurable per tenant. |
| H6 | **Audit Trail** | Every action logged: upload, view, export, settings change. Immutable audit table. Query API for compliance. |
| H7 | **Helm Chart + Production Docker** | K8s Helm chart (API + workers + Redis + PostgreSQL). Docker Compose for smaller deploys. Health/readiness probes. |
| H8 | **Performance** | DB indexing, connection pooling, Redis response caching. Frontend: lazy routes, virtual scrolling, bundle splitting. Target: <200ms p95 API, <2s page load. |
| H9 | **Comprehensive Test Suite** | Integration tests with simulated LLM. Load tests (Locust). Security scan (Bandit). Accessibility (axe-core). Coverage target: 85%+. |
| H10 | **Documentation Site** | Auto-generated API reference from OpenAPI. User guide with screenshots. Developer guide for SDK/plugins. GitHub Pages deploy. |

**Frontend:**
- Admin panel (tenant/user/role management)
- Audit log viewer
- Settings page (PII toggle, notification prefs, API key management)
- Performance: lazy routes, skeleton screens, virtual scroll for 10K+ items

**Tests:** `test_phase_h_enterprise.py` — tenant isolation, RBAC enforcement, PII redaction, audit trail.

---

## 6. Key Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Temporal alignment accuracy | Core functionality breaks | Start simple, iterate with evaluation |
| Vision model costs at scale | Budget blowout | Local models (Qwen-VL, LLaVA) as fallback |
| ASR accuracy on noisy calls | Bad downstream extraction | Multi-model ensemble, confidence filtering |
| Fine-tuning data quality | Model doesn't improve | Active learning loop, quality annotations |
| Real-time latency budget | Streaming unusable | Profile early, optimize critical path |

---

## 7. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-20 | Python as primary language | ML ecosystem, team expertise |
| 2026-03-20 | Start with batch, add streaming later | Reduce early complexity |
| 2026-03-20 | OpenTelemetry from day one | Observability is a core learning goal |
| 2026-03-20 | Prompt-based extraction first, fine-tune later | Need data before fine-tuning |
| 2026-03-20 | DeepEval for evaluation framework | Already initialized in project |
| 2026-03-21 | Webhook delivery before all other integrations | Unblocks Zapier, Slack, Notion, CRM without tight coupling |
| 2026-03-21 | Speaker diarization is Phase A1 priority | Unlocks coaching, talk ratio, HR vertical, rep benchmarks |
| 2026-03-21 | Custom schema builder unlocks vertical packs | One mechanism replaces 7 vertical-specific extraction models |
| 2026-03-21 | Python SDK before vertical UI packs | Developer adoption compounds; verticals can be schema files |
| 2026-03-21 | Chroma for vector store (dev), Pinecone for prod | Zero-dependency local dev path; swap at scale |
| 2026-03-21 | Phase E = AI-Native Core before anything else | Nothing matters if extraction/synthesis is keyword-based. Wire real LLMs first. |
| 2026-03-21 | Phase F = Real workflows, auth, demo data, polish | AI is meaningless without usable UX, onboarding, and demo-ability |
| 2026-03-21 | Phase G = Competitive moats (diff engine, live copilot, pattern mining) | Features no competitor has. This is the "top 1%" differentiator. |
| 2026-03-21 | Phase H = Enterprise scale (multi-tenant, SSO, RBAC, PII, audit) | Production-grade for deployment. Security and compliance last because they need stable feature surface. |
| 2026-03-21 | Honest assessment: Phases A-D were structure, not intelligence | All extraction/synthesis was rule-based. Must wire LLMs before claiming AI product. |
| 2025-07-17 | Phases E/F/G/H fully implemented | 146 total tests across 4 phases. 26 new modules + Helm chart. LLM router, auth, enterprise features, competitive moats all working. |
| 2025-07-18 | Phase I = State Persistence & Data Integrity | All in-memory stores (audit, notifications, annotations, active learning, auth, tenants) wired to async DB persistence. Alembic migrations. Stable AUTH_SECRET. 40 new tests, 603 total passing. |
| 2025-07-19 | Phase J = Frontend Completion & Real UX | 7 new API routes, 8 new React pages, notification bell. 25 total pages, 28 API route modules. 36 tests passing. |
| 2025-07-19 | Phase K = Real Integrations & Production Streaming | Deepgram WebSocket ASR adapter, S3/Local storage abstraction, config consolidation. 31 tests passing. |
| 2025-07-19 | Phase L = CI/CD, Security & Production Hardening | GitHub Actions CI (4 jobs), security headers (8 headers), health probes, Docker Compose with 3 services. 18 tests passing. |
| 2025-07-19 | Phase M = Documentation, SDK & Developer Experience | Python SDK (zero-dependency, 13 methods), deployment guide, architecture docs, API reference, README update. 27 tests passing. Total: 688+ tests. |
