# DealFrame — Expansion Vision
> Last updated: 2026-03-26  
> Status: Planning document — read before building

---

## The Core Claim (worth repeating)

> **Any meeting, lecture, walkthrough, hearing, session, or call produces unstructured video.**  
> DealFrame turns video into a **machine-readable, queryable, actionable intelligence graph.**

That one capability is broadly useful across a dozen industries, three user scales, and dozens of integration targets. The plan below maps all of them, orders them by value and buildability, and defines five expansion phases.

---

## PART 1 — INDUSTRY MAP

### 1.1 Sales & Revenue Intelligence (current + deepest vertical)

**What's built**: objection detection, risk scoring, topic tagging, decision signals, per-segment sentiment.

**What's missing**:
- Talk/listen ratio per speaker
- Competitor mention tracking + alerts
- Pricing signal extraction (exact numbers mentioned, negotiation moves)
- Deal velocity scoring ("this call is 30% worse than your average won deal")
- Rep-to-rep coaching benchmark
- Preview of next-call recommendations ("bring a case study on security")
- Auto-generated follow-up email with evidence from the call
- CRM auto-enrichment (write Salesforce fields from call data)
- Gong/Chorus replacement API

**Industries**: SaaS, insurance, real estate, financial advisory, recruiting agencies, enterprise software, media sales.

---

### 1.2 Legal & Compliance

Depositions, contract negotiation recordings, arbitration hearings, internal investigation calls — all produce structured video with strict evidentiary needs.

**Extraction schema needed** (different from sales):
- Speaker roles (attorney, witness, judge, examiner)
- Contradiction detection ("on page 45 you said X; at 12:32 you said Y")
- Admission detection — legally significant statements
- Exhibit references ("Plaintiff's Exhibit 3")
- Objection log (legal objections, not sales objections)
- Credibility signals (hesitation, correction rate, confidence)

**Key differentiator**: timestamped, citable extraction. Every fact traceable to `[12:32 — Witness A]`.

**Users**: paralegals, associates, eDiscovery teams, legal ops, compliance officers.

**Integrations**: Relativity, iManage, Clio, contract management systems.

---

### 1.3 Healthcare & Clinical

Telemedicine sessions, patient intake calls, clinical education videos, drug rep–physician interactions.

**Extraction schema**:
- Symptom mentions (structured as SNOMED concepts)
- Medication names and dosages
- Patient concerns / objections to treatment
- Follow-up action items ("schedule MRI", "return in 2 weeks")
- Informed consent completeness check
- Provider communication quality score

**Compliance requirement**: HIPAA mode — PII redaction before storage, on-premise deployment only, audit log.

**Users**: clinical documentation teams, health system administrators, pharma field teams, medical educators.

**Integrations**: Epic, Cerner (via FHIR), Veeva CRM.

---

### 1.4 Education & Learning

Lecture recordings, online course videos, tutoring sessions, webinars, coding bootcamp reviews.

**Extraction schema**:
- Concept explanations (extract definitions, examples, analogies)
- Engagement signals (pacing, repetition, questions asked)
- Knowledge check moments (quiz questions, call-to-understand)
- Topic progression map (what was covered, in what order)
- Confusion signals (repeated questions on same topic, correction rate)
- Prerequisite detection ("before we can understand X, you need to know Y")

**Use cases**:
- *Students*: auto-generate study notes from lecture recordings
- *Professors*: measure which concepts get the most backtracking / confusion
- *Course makers*: find which video segments have the highest drop rate
- *Corporate L&D*: training completion verification + comprehension scoring

**Integrations**: Canvas, Moodle, Coursera, Teachable, Google Classroom.

---

### 1.5 Product & UX Research

User interviews, usability testing sessions, think-aloud protocols, focus groups, beta feedback calls.

**Extraction schema**:
- Pain points (structured by feature/workflow area)
- Positive signals (delight moments, "this is great")
- Confusion moments (hesitation + backtracking + verbal expression)
- Feature requests (explicit asks)
- Competitive comparisons mentioned
- Task success / failure classification

**Key capability**: search across 100 user interviews — "What did people say about onboarding?"

**Users**: UX researchers, product managers, founders, design teams.

**Integrations**: Dovetail, Notion, Figjam, Jira.

---

### 1.6 Financial Services

Earnings calls, investor roadshow recordings, financial advisor–client meetings, M&A diligence calls, board meetings.

**Extraction schema**:
- Forward-looking statements (flagged for legal)
- Guidance mentions (explicit numbers)
- Risk disclosures
- Sentiment vs equity price correlation
- Competitive positioning statements
- Analyst question themes

**Compliance**: MiFID II, SEC recording requirements, PII handling.

**Users**: hedge fund analysts, IR teams, compliance officers, wealth managers.

**Integrations**: Bloomberg, Refinitiv, Salesforce Financial Services Cloud.

---

### 1.7 HR & Talent

Job interviews, performance reviews, town halls, onboarding sessions, management 1:1s (with consent).

**Extraction schema**:
- Candidate competency signals (structured against job rubric)
- DEI fairness score (are similar candidates asked similar questions?)
- Performance concern vs positive feedback ratio
- Action items from review ("grow in leadership by Q3")
- Culture fit signals
- Engagement score in town halls

**Risk**: highest privacy/ethics sensitivity. Requires explicit consent infrastructure.

**Users**: recruiters, HR business partners, L&D, talent operations.

**Integrations**: Greenhouse, Lever, Workday, ADP.

---

### 1.8 Customer Success & Support

QBR recordings, support escalation calls, renewal conversations, onboarding calls, churn risk conversations.

**Extraction schema** (same as sales base but with CS lens):
- Health score signals (product usage mentions, satisfaction signals)
- Churn risk indicators ("we might not renew", "our team isn't using this")
- Expansion signals ("we're growing the team", "we need more seats")
- Support ticket themes mentioned on call
- Executive escalation risk

**Users**: CSMs, CS ops, account managers, VP of Customer Success.

**Integrations**: Gainsight, Totango, Salesforce, Zendesk, ChurnZero.

---

### 1.9 Journalism, Media & Research

Press conferences, earnings calls (public), political debates, academic conference talks, documentary footage analysis.

**Extraction schema**:
- Quote extraction (attributable, citable)
- Fact claim detection (for fact-checking pipeline)
- Speaker stance on topic X over time
- Claim-vs-evidence structure
- Narrative frame detection

**Users**: journalists, fact-checkers, academic researchers coding qualitative data, documentary editors.

**Integrations**: Hypothesis (annotation), Zotero, MediaCloud.

---

### 1.10 Real Estate & Property

Property walkthroughs, client consultation recordings, virtual tours.

**Extraction schema**:
- Feature mentions (bedrooms, bathrooms, kitchen, storage)
- Client priority signals ("we really need a home office")
- Objection signals ("it's over our budget")
- Comparison to prior properties
- Urgency signals

---

## PART 2 — USER TIER MAP

### Tier 1: Freelancer / Student / Solo

**Who**: independent researchers, consultants, students, content creators, solo founders  
**Volume**: 1–10 videos/month  
**Needs**: simple upload → structured output → export  
**Pain point**: can't afford Gong ($1,000+/mo), needs something lightweight, pay-per-use

**Capabilities to build**:
- Free tier: 3 videos/month
- One-click export: PDF, Markdown, Notion page
- Chrome extension — adds "Analyze in DealFrame" button to Loom, Zoom cloud recording pages
- Obsidian plugin — sync analysis as notes
- No-code Zapier integration (video URL → analysis → send to Google Sheet)
- Dashboard shareable link (send analysis to client without account)

---

### Tier 2: Team / SMB / Departmental

**Who**: sales teams (5–50 reps), UX research teams, training departments, small law firms  
**Volume**: 100–1,000 videos/month  
**Needs**: shared workspace, integrations with existing tools, search across team's library

**Capabilities to build**:
- Team workspace with role-based access
- Shared search: "find all calls where pricing was raised"
- CRM integration (push to Salesforce/HubSpot automatically)
- Slack bot: daily digest of risky calls flagged overnight
- Zoom auto-ingest (webhook on recording complete → auto-process)
- Google Meet auto-ingest via Google Calendar connector
- CSV export for analytics
- Annotation & tagging (human labels on segments for fine-tuning)
- Custom extraction schemas (define your own fields via YAML)

---

### Tier 3: Enterprise / Platform

**Who**: large sales orgs, health systems, law firms, financial institutions, platform builders  
**Volume**: 10,000+ videos/month  
**Needs**: self-hosted, compliance, SSO, custom models, API-first, white-label

**Capabilities to build**:
- Multi-tenant architecture (isolated DB per tenant)
- SSO/SAML (Okta, Azure AD, Google Workspace)
- HIPAA compliance mode (on-premise, PII redaction, audit trail)
- Self-hosted Helm chart (Kubernetes)
- Custom extraction model per tenant (fine-tuned on their data)
- White-label (SDK embeds in their product)
- Priority API (SLA-backed, rate limits configurable)
- Batch API (submit 1,000 videos, get webhook on completion)
- Grafana dashboard templates for their ops teams
- Data residency (EU, US-East, etc.)

---

## PART 3 — INTEGRATION CATALOG

### 3.1 Video Ingestion Sources

| Source | Integration Type | Priority |
|--------|-----------------|----------|
| Zoom | Recording webhook + Zoom Apps API | P0 |
| Google Meet | Google Calendar watch + Drive recorder | P0 |
| Microsoft Teams | Teams Apps + Graph API | P1 |
| Loom | Webhook on upload + Loom API | P1 |
| Webex | REST API | P2 |
| YouTube / Vimeo | Video URL input → yt-dlp | P2 |
| S3 / GCS bucket | Event notification → auto-ingest | P1 |
| Gong | Pull recordings from Gong API (shadow mode) | P2 |
| Chorus | Pull recordings from Chorus API | P2 |

### 3.2 CRM & Revenue

| System | What we write | Priority |
|--------|--------------|----------|
| Salesforce | Activity record, custom fields: risk_score, objections, decision_signals, sentiment | P0 |
| HubSpot | Engagement record, note, contact property update | P0 |
| Pipedrive | Note + activity + custom field update | P1 |
| Close CRM | Activity + lead note | P1 |
| Attio | Record update via API | P2 |
| Outreach | Sequence intelligence update | P2 |

### 3.3 Productivity & Knowledge

| System | What we send | Priority |
|--------|-------------|----------|
| Notion | Create database record per video (all fields as properties) | P0 |
| Slack | Alert on high-risk call, daily digest, mention bot | P0 |
| Linear | Create issue per action item extracted | P1 |
| Jira | Create ticket per action item | P1 |
| Confluence | Create page with meeting notes | P1 |
| Google Docs | Auto-generate meeting notes doc | P1 |
| Obsidian | Plugin: sync as markdown notes | P2 |
| Roam Research | Import structured blocks | P3 |

### 3.4 AI & Model Providers

| Provider | Usage | Integration Type |
|----------|-------|-----------------|
| OpenAI | GPT-4o extraction, Whisper ASR, GPT-4o Vision | REST API (existing) |
| Anthropic | Claude Sonnet/Opus extraction, Claude Vision | REST API (existing) |
| Google | Gemini 1.5 Pro extraction (long context), Google Speech-to-Text | REST API |
| Groq | Ultra-fast inference for real-time extraction (Llama-3, Mixtral) | REST API |
| Deepgram | Low-latency streaming ASR | WebSocket (existing stub) |
| AssemblyAI | Batch ASR with speaker labels, sentiment, chapters | REST API |
| ElevenLabs | Voice-to-voice synthesis (coaching playback) | REST API |
| Cohere | Embedding model for semantic search | REST API |
| Pinecone / Weaviate | Vector store for semantic search at scale | SDK |
| Replicate | Run open models (LLaVA, Qwen-VL) in cloud | REST API |
| Together.ai | Fine-tuned model hosting | REST API |
| Modal | Serverless GPU for local model inference | Python SDK |

### 3.5 Agent & Automation Frameworks

| Framework | Integration | Priority |
|-----------|------------|----------|
| LangChain | `DealFrameTool` — call DealFrame from any chain | P0 |
| LlamaIndex | `DealFrameReader` — index video library as LlamaIndex documents | P0 |
| AutoGPT | Plugin: process a video URL | P1 |
| OpenAI Assistants | Function tool definition for DealFrame API | P1 |
| Zapier | Zap: "Video uploaded → analyze → update CRM" | P0 |
| Make.com | Module: process video + route output | P1 |
| n8n | Node: DealFrame analyze | P1 |
| Cursor / Windsurf | Extension: analyze screen recording of coding session | P2 |

### 3.6 Analytics & Observability

| Tool | Integration | Priority |
|------|------------|----------|
| Grafana | Pre-built dashboard templates | P1 |
| Metabase | BI connector to analysis DB | P1 |
| Amplitude | Event tracking (product analytics) | P2 |
| Datadog | Custom metrics forwarder | P2 |

---

## PART 4 — NEW PLATFORM CAPABILITIES

These are net-new capabilities beyond the current pipeline — each is a standalone buildable unit.

### 4.1 Speaker Intelligence Module
**What**: per-speaker analytics beyond transcription.
- Talk-to-listen ratio (rep vs prospect)
- Words per minute (pace)
- Interruption detection
- Question rate (how often does each party ask questions?)
- Filler word rate ("um", "uh", "like") → proxy for confidence
- Energy/engagement score (volume variance over time)

**How to build**: speaker diarization (pyannote-audio already planned) → per-speaker word windows → compute metrics per speaker per call → aggregate across calls for benchmarking.

### 4.2 Auto-Summary Engine
**What**: multiple summary types from a single video:
- **Executive summary** (3 bullets, 30 words max)
- **Action items only** (numbered, owner assigned)
- **Full meeting notes** (structured, shareable)
- **Deal brief** (sales-specific: situation, next steps, risk)
- **Custom template** (user provides Handlebars/Mustache template)

**How to build**: pass full `VideoIntelligence` output + selected summary type to Claude/GPT-4o with tailored prompt → stream response → cache in DB. Template renderer for custom layouts.

### 4.3 Clip Extractor
**What**: given a processed video, auto-identify and export the N most significant moments as short clips.
- "Extract the 3 most important moments from this call"
- "Find all competitor mentions and export as clips"
- "Show me every moment the customer objected"

**How to build**: extraction results have timestamps → map back to original video → FFmpeg cut clips → serve from `/clips/{job_id}/{clip_id}`. Clip scoring based on risk score + sentiment delta.

### 4.4 Video Q&A Agent
**What**: chat interface over your entire video library.
- "What have customers said about pricing in the last 30 days?"
- "Which rep handles security objections best?"
- "Summarize what we know about competitor X from our calls"

**How to build**: embed all extraction results into vector store (Chroma/Pinecone) → LangChain RAG chain with DealFrame retriever → answer with citations `[Call 2026-03-15 @ 12:32]`.

### 4.5 Deal Risk Agent
**What**: autonomous Slack bot that monitors your processed calls and alerts when a deal is at risk.
- Runs nightly sweep of all calls processed that day
- Computes risk delta (this call vs previous call for same deal)
- Posts Slack message: "⚠️ Deal with Acme Corp: risk jumped 40% — 3 new objections identified. See call at 14:22, 18:05, 31:00."

**How to build**: Celery/cron scheduled job → query DB for new calls → compare risk trajectory → Slack Incoming Webhook.

### 4.6 Coaching Engine
**What**: rep-specific performance analytics and actionable coaching.
- Compare a rep's calls to top-quartile calls
- Measure: talk ratio, objection handling speed, close rate vs pipeline behavior
- Generate coaching card: "Your pricing objection handling is 2x slower than top performers. Here are 3 examples of how they handled it."

**How to build**: per-speaker metrics + benchmark comparisons + GPT-4o narrative generation per coaching dimension.

### 4.7 Custom Schema Builder
**What**: no-code UI to define your own extraction fields.
- User defines a YAML schema: `field_name: topic | sentiment | custom_string | bool`
- System generates a prompt template from the schema
- Fine-tunes on user's own labeled data (BYOD fine-tuning)

**How to build**: YAML schema → Pydantic model generator → prompt constructor → extraction model adapter. UI: form builder in React.

### 4.8 Knowledge Graph
**What**: extract entities, relationships, and facts across all videos into a queryable graph.
- Entity types: Person, Company, Product, Feature, Price, Date
- Relationships: `[Rep] mentioned [Product]`, `[Customer] objected [Price]`, `[Company] competes_with [Competitor]`
- Answers: "What do I know about Acme Corp across all calls?"

**How to build**: NER pass on all extracted text → graph DB (NetworkX → Neo4j at scale) → graph query API.

### 4.9 Meeting Preparation Agent
**What**: before a scheduled call, auto-generate a prep brief.
- Pull CRM data for the company/contact
- Search past calls with this company
- Generate: "Last call (2026-03-01): raised pricing objections, mentioned competitor X. Recommended talking points: ..."

**How to build**: calendar webhook (Google/Outlook) → CRM lookup → DealFrame search for past calls with same company → briefing prompt → deliver via email/Slack before the meeting.

### 4.10 Batch Processing API
**What**: enterprise-grade bulk video processing.
- `POST /batch` with list of video URLs or S3 paths
- Async processing with webhook on completion
- Priority queuing (paid tier gets priority workers)
- Progress endpoint with per-video status

**How to build**: Celery task queue + Redis broker, or Temporal workflow engine (replaces current threading approach at scale).

---

## PART 5 — EXPANSION PHASES

### Phase A — Platform Primitives (Weeks 1–4)
*Make DealFrame a platform, not just a pipeline.*

**Deliverables**:

| # | Component | What it enables |
|---|-----------|----------------|
| A1 | **Speaker Diarization** (pyannote-audio) | Per-speaker analytics across all downstream modules |
| A2 | **Auto-Summary Engine** (multi-template) | First killer output beyond raw JSON |
| A3 | **Clip Extractor API** | `/clips/{job_id}` — exportable video moments |
| A4 | **Custom Schema Builder** (YAML → extraction) | Any vertical, any field definition |
| A5 | **Webhook Delivery System** | Push results to any URL on completion |
| A6 | **Python SDK** (`pip install temporalos`) | Developers can integrate with 3 lines |
| A7 | **REST API versioning** (v2 with proper pagination, cursors) | Production-grade API |

**Frontend additions**: Summary panel on Results page, Clip viewer, Schema builder UI.

---

### Phase B — Integrations (Weeks 5–8)
*Meet users where they already work.*

**Deliverables**:

| # | Integration | Mechanism |
|---|------------|-----------|
| B1 | **Zoom auto-ingest** | Zoom webhook → auto-submit recording URL |
| B2 | **Google Meet auto-ingest** | Google Calendar push notification → Drive link → submit |
| B3 | **Slack bot** | Slash command `/temporalos search <query>`, daily risk digest |
| B4 | **Notion exporter** | OAuth flow → create DB record per video |
| B5 | **Salesforce enrichment** | OAuth → write custom Activity + fields on Contact/Opportunity |
| B6 | **HubSpot enrichment** | OAuth → write Engagement + note |
| B7 | **Zapier app** | Trigger: video processed. Action: push analysis to any Zapier-connected app |
| B8 | **LangChain tool** | `DealFrameTool` with full docstring for LLM function calling |
| B9 | **LlamaIndex reader** | `DealFrameReader` — turns video library into LlamaIndex index |

---

### Phase C — Intelligence Layer (Weeks 9–12)
*Turn stored extractions into actionable intelligence.*

**Deliverables**:

| # | Component | What it enables |
|---|-----------|----------------|
| C1 | **Video Q&A Agent** | Chat with your entire call library |
| C2 | **Deal Risk Agent** | Autonomous Slack alerts on deal risk changes |
| C3 | **Coaching Engine** | Per-rep performance benchmarks + coaching cards |
| C4 | **Knowledge Graph** | Entity/relationship graph across all videos |
| C5 | **Meeting Preparation Agent** | Auto-brief before scheduled calls |
| C6 | **Competitor Intelligence Mode** | Track all competitor mentions, extract feature comparisons |

---

### Phase D — Vertical Packs (Weeks 13–18)
*Industry-specific extraction schemas, prompts, and UI.*

**Deliverables** (each is a "vertical pack" — schema + prompt + UI preset + example outputs):

| Pack | Schema highlights | Target user |
|------|------------------|-------------|
| **Sales Pack** (deepen existing) | Talk ratio, pricing detection, deal scoring, rep benchmarks | AE, SDR, Sales Manager |
| **UX Research Pack** | Pain point coding, feature request extraction, usability scores | Product Manager, UX Researcher |
| **Legal Pack** | Admission detection, exhibit references, contradiction flagging | Paralegal, Associate, eDiscovery |
| **Education Pack** | Concept extraction, study notes, confusion detection | Student, Professor, L&D |
| **CS & Churn Pack** | Health signals, expansion indicators, churn risk score | CSM, Account Manager |
| **HR Pack** | Competency tagging, rubric scoring, DEI fairness audit | Recruiter, HRBP |
| **Finance Pack** | Guidance extraction, analyst sentiment, disclosure flags | Analyst, IR, Compliance |

---

### Phase E — Enterprise Platform (Weeks 19–26)
*Scale to 10,000+ videos/month, multi-tenant, compliance-ready.*

**Deliverables**:

| # | Capability | Complexity |
|---|-----------|-----------|
| E1 | **Multi-tenant DB isolation** | Medium |
| E2 | **SSO/SAML** (Okta, Azure AD) | Medium |
| E3 | **HIPAA compliance mode** (PII redaction, on-prem) | High |
| E4 | **Celery/Temporal task queue** (replace threading) | Medium |
| E5 | **Self-hosted Helm chart** | High |
| E6 | **Custom model per tenant** (fine-tuned adapter isolation) | High |
| E7 | **Batch API** with priority queuing | Medium |
| E8 | **White-label SDK** (embed in partner product) | Medium |
| E9 | **Grafana dashboard templates** | Low |
| E10 | **SOC2 Type 2 audit trail** | High |

---

## PART 6 — BUILD PRIORITY MATRIX

```
                    IMPACT
              LOW          HIGH
           ┌─────────────┬──────────────┐
    HIGH   │             │ A2 Summary   │
    EFFORT │             │ C1 Q&A Agent │
           │             │ B1 Zoom      │
           └─────────────┼──────────────┤
    LOW    │ B9 LlamaIndex│ A5 Webhook   │
    EFFORT │ A6 Python SDK│ B3 Slack bot │
           │             │ A4 Custom Sch│
           │             │ B4 Notion    │
           └─────────────┴──────────────┘
```

**Build order rule**: Low effort + High impact first. Phase A and B deliver the most value with fewest dependencies.

Recommended next 10 items to build (ordered):

1. `A5` — Webhook delivery (unblocks all integrations)
2. `A2` — Auto-summary engine (first "wow" output beyond raw JSON)
3. `A4` — Custom schema builder (unlocks every vertical)
4. `A1` — Speaker diarization (unlocks coaching, talk ratio, HR pack)
5. `B3` — Slack bot (daily active usage driver)
6. `B1` — Zoom auto-ingest (zero-friction pipeline entry)
7. `A6` — Python SDK (developer adoption)
8. `B4` — Notion exporter (solo + SMB killer app)
9. `B5` — Salesforce enrichment (enterprise justification)
10. `C1` — Video Q&A Agent (platform-defining capability)

---

## PART 7 — TECHNICAL ARCHITECTURE UPGRADES NEEDED

### 7.1 Task Queue (current: threading → target: Celery + Redis)
Current threading approach hits limits at ~10 concurrent videos. Celery with Redis broker gives:
- Priority queues (enterprise tier jumps queue)
- Retry with backoff
- Progress events
- Worker auto-scaling

### 7.2 Vector Store (new: Chroma → Pinecone at scale)
- Embedded Chroma for local/dev
- Pinecone / Weaviate for production (semantic search at 100k+ documents)
- Embedding: `text-embedding-3-small` (OpenAI) or `cohere-embed-v3` (multi-language)

### 7.3 Graph Database (new capability)
- NetworkX for local knowledge graph
- Neo4j for production graph queries
- Exposed via Cypher query API

### 7.4 Schema Registry
- Extraction schemas stored in DB (`schemas` table)
- Schema versioning (v1, v2 for same schema)
- Schema marketplace (share schemas across teams)

### 7.5 Multi-Tenancy
- DB: row-level `tenant_id` filter OR separate SQLite files per tenant (easier)
- API: tenant from JWT claim, middleware adds filter
- Storage: S3 bucket/prefix per tenant

---

## PART 8 — MONEN/PRICING MODEL IDEAS

| Tier | Price | Limits |
|------|-------|--------|
| **Free** | $0 | 3 videos/month, 30min max, watermarked PDF |
| **Solo** | $19/mo | 25 videos/month, all exports, API access |
| **Team** | $99/mo | 150 videos/month, 5 seats, Slack + Notion integrations |
| **Pro** | $299/mo | 500 videos/month, 20 seats, CRM integrations, custom schema |
| **Enterprise** | Custom | Unlimited, self-hosted, SSO, HIPAA, SLA |

**Pay-per-video** (freelancer option): $0.99/video under 30 min, $1.99/video 30–90 min.

---

## PART 9 — COMPETITIVE LANDSCAPE

| Product | Focus | Weakness vs DealFrame |
|---------|-------|----------------------|
| Gong.io | Sales call intelligence | $1,200+/seat/year, closed, no custom schemas, no fine-tuning |
| Chorus.ai (ZoomInfo) | Sales call intelligence | Same as Gong, acquisition baggage |
| Otter.ai | Transcription | No structured extraction, no vision |
| Fireflies.ai | Meeting notes | No structured signals, no risk scoring |
| Dovetail | UX research | No video pipeline, manual coding only |
| Grain | Sales highlights | Clip extraction only, no intelligence |
| Recall.ai | Recording infrastructure | Infrastructure only, no intelligence layer |

**DealFrame moat**: open-source core, fine-tunable models, custom schemas, multimodal (vision + audio), developer-first API, self-hostable.

---

## Summary

DealFrame is 10% built. The core pipeline works. What's missing:

1. **The outputs people share** (summaries, clips, Notion pages) – Phase A
2. **The integrations people live in** (Zoom, Slack, Salesforce) – Phase B  
3. **The intelligence that scales** (Q&A agent, risk bot, coaching) – Phase C
4. **The verticals that pay** (legal, healthcare, finance) – Phase D
5. **The infrastructure that enterprises need** (SSO, HIPAA, multi-tenant) – Phase E

The first 10 items above can be built in 4–6 weeks and will transform DealFrame from a demo project into a product people want to pay for.
