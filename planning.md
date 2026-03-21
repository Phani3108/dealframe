# TemporalOS — Planning & Architecture

> Last updated: 2026-03-21

> **See [EXPANSION.md](./EXPANSION.md) for the full expansion vision — industries, integrations, user tiers, and the 5-phase build plan.**

---

## 1. Vision Statement

Transform raw video into structured, queryable decision intelligence. A sales call isn't just audio — it's a timestamped graph of intent, objection, sentiment, and visual context. TemporalOS makes that graph machine-consumable.

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

### 🔷 Phase A: Platform Primitives (NEXT)
*See EXPANSION.md §5 Phase A for full spec.*
- [ ] A1 — Speaker diarization (pyannote-audio)
- [ ] A2 — Auto-summary engine (executive / action-items / meeting-notes / deal-brief templates)
- [ ] A3 — Clip extractor API (FFmpeg cut + serve per timestamp range)
- [ ] A4 — Custom schema builder (YAML → extraction prompt → Pydantic model)
- [ ] A5 — Webhook delivery system (POST results to any URL on completion)
- [ ] A6 — Python SDK (`pip install temporalos`)
- [ ] A7 — REST API v2 (pagination cursors, versioned routes)

### 🔷 Phase B: Integrations
*See EXPANSION.md §5 Phase B for full spec.*
- [ ] B1 — Zoom auto-ingest (recording webhook)
- [ ] B2 — Google Meet auto-ingest (Calendar push + Drive)
- [ ] B3 — Slack bot (slash command + daily digest)
- [ ] B4 — Notion exporter (OAuth + DB record per video)
- [ ] B5 — Salesforce enrichment
- [ ] B6 — HubSpot enrichment
- [ ] B7 — Zapier app
- [ ] B8 — LangChain tool
- [ ] B9 — LlamaIndex reader

### 🔷 Phase C: Intelligence Layer
- [ ] C1 — Video Q&A agent (RAG over extraction DB)
- [ ] C2 — Deal risk agent (Slack alerts on risk changes)
- [ ] C3 — Coaching engine (rep benchmarks + coaching cards)
- [ ] C4 — Knowledge graph (entity/relationship extraction)
- [ ] C5 — Meeting preparation agent (pre-call brief)
- [ ] C6 — Competitor intelligence mode

### 🔷 Phase D: Vertical Packs
- [ ] Sales Pack (deepen + talk ratio + deal scoring)
- [ ] UX Research Pack (pain point coding, usability)
- [ ] Legal Pack (admissions, contradictions, exhibits)
- [ ] Education Pack (concept extraction, study notes)
- [ ] CS & Churn Pack (health signals, expansion indicators)
- [ ] HR Pack (competency tagging, DEI fairness)
- [ ] Finance Pack (guidance, disclosures, analyst sentiment)

### 🔷 Phase E: Enterprise Platform
- [ ] Multi-tenant architecture (row-level isolation)
- [ ] SSO/SAML (Okta, Azure AD)
- [ ] HIPAA compliance mode (PII redaction, audit trail)
- [ ] Celery/Temporal task queue
- [ ] Self-hosted Helm chart
- [ ] Custom model per tenant
- [ ] Batch API with priority queuing
- [ ] White-label SDK

---

## 5. Expansion Ideas (Beyond Core)

> Full expansion vision in **[EXPANSION.md](./EXPANSION.md)**.

### Industries
Sales, Legal, Healthcare, Education, UX Research, Financial Services, HR, Customer Success, Journalism, Real Estate.

### User Tiers
- **Solo/Freelancer/Student**: pay-per-video, Chrome extension, Obsidian plugin, shareable link
- **Team/SMB**: shared workspace, Zoom auto-ingest, Slack bot, CRM integrations
- **Enterprise**: multi-tenant, SSO, HIPAA, self-hosted, custom models, batch API

### New Platform Capabilities (see EXPANSION.md §4)
- Speaker Intelligence (talk ratio, pace, interruptions)
- Auto-Summary Engine (executive / action-items / meeting-notes)
- Clip Extractor (timestamp → video clip)
- Video Q&A Agent (RAG over video library)
- Deal Risk Agent (Slack alerts)
- Coaching Engine (rep benchmarks)
- Custom Schema Builder (YAML → extraction)
- Knowledge Graph (entity/relationship)
- Meeting Preparation Agent (pre-call brief)
- Batch Processing API

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
