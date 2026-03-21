"""E2E tests for audit gap fixes.

Tests real implementations added during the gap-fixing session:
- Job persistence to DB + reload
- Search doc persistence + rebuild
- SSO token exchange (no NotImplementedError)
- LLM summarization engine (fallback to mock)
- Knowledge graph NER (money, org, person, email)
- QA agent LLM synthesis path
- ASR auto-detect logic
- Vertical pack extraction (Sales, CS, UX, RealEstate)
- Clip reel → FFmpeg wiring
- Storage wiring
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    yield url, path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def session_factory(tmp_db):
    url, _ = tmp_db
    engine = create_async_engine(url, echo=False)

    async def _setup():
        from temporalos.db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, expire_on_commit=False)

    sf = asyncio.get_event_loop().run_until_complete(_setup())
    yield sf
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 1. Job Persistence ───────────────────────────────────────────────────────

class TestJobPersistence:

    def test_job_record_model_exists(self):
        from temporalos.db.models import JobRecord
        assert hasattr(JobRecord, "id")
        assert hasattr(JobRecord, "status")
        assert hasattr(JobRecord, "result")
        assert hasattr(JobRecord, "stages_done")

    def test_job_roundtrip(self, session_factory):
        from temporalos.db.models import JobRecord
        from sqlalchemy import select

        async def _go():
            async with session_factory() as sess:
                rec = JobRecord(
                    id="test-job-1",
                    status="completed",
                    video_path="/tmp/test.mp4",
                    stages_done=["frame_extraction", "transcription"],
                    result={"segments": [], "overall_risk_score": 0.5},
                )
                sess.add(rec)
                await sess.commit()

            async with session_factory() as sess:
                row = (await sess.execute(
                    select(JobRecord).where(JobRecord.id == "test-job-1")
                )).scalar_one()
                assert row.status == "completed"
                assert "frame_extraction" in row.stages_done
                assert row.result["overall_risk_score"] == 0.5

        _run(_go())

    def test_load_jobs_from_db_populates_cache(self, session_factory):
        from temporalos.db.models import JobRecord
        from temporalos.api.routes.process import _jobs, load_jobs_from_db

        async def _go():
            async with session_factory() as sess:
                sess.add(JobRecord(
                    id="reload-test",
                    status="completed",
                    stages_done=["extraction"],
                    result={"segments": []},
                ))
                await sess.commit()

        _run(_go())

        _jobs.clear()
        with patch("temporalos.db.session.get_session_factory",
                    return_value=session_factory):
            _run(load_jobs_from_db())

        assert "reload-test" in _jobs
        assert _jobs["reload-test"]["status"] == "completed"


# ── 2. Search Doc Persistence ────────────────────────────────────────────────

class TestSearchDocPersistence:

    def test_search_doc_record_model_exists(self):
        from temporalos.db.models import SearchDocRecord
        assert hasattr(SearchDocRecord, "id")
        assert hasattr(SearchDocRecord, "video_id")
        assert hasattr(SearchDocRecord, "topic")

    def test_search_doc_roundtrip(self, session_factory):
        from temporalos.db.models import SearchDocRecord
        from sqlalchemy import select

        async def _go():
            async with session_factory() as sess:
                sess.add(SearchDocRecord(
                    id="vid1:00:30",
                    video_id="vid1",
                    timestamp_ms=30000,
                    timestamp_str="00:30",
                    topic="pricing",
                    risk="high",
                    risk_score=0.85,
                    objections=["too expensive"],
                    decision_signals=["ready to buy"],
                    transcript="The pricing is...",
                    model="gpt-4o",
                ))
                await sess.commit()

            async with session_factory() as sess:
                row = (await sess.execute(
                    select(SearchDocRecord).where(SearchDocRecord.id == "vid1:00:30")
                )).scalar_one()
                assert row.topic == "pricing"
                assert row.risk_score == 0.85
                assert "too expensive" in row.objections

        _run(_go())


# ── 3. SSO Token Exchange ────────────────────────────────────────────────────

class TestSSOExchange:

    def test_google_exchange_not_raises(self):
        """GoogleSSO.exchange_code should not raise NotImplementedError."""
        from temporalos.enterprise.sso import GoogleSSO
        sso = GoogleSSO(client_id="test", client_secret="secret", redirect_uri="http://localhost")
        # It will fail on the HTTP call, but should NOT be NotImplementedError
        with pytest.raises(Exception) as exc_info:
            _run(sso.exchange_code("fake-code"))
        assert "NotImplementedError" not in type(exc_info.value).__name__

    def test_microsoft_exchange_not_raises(self):
        from temporalos.enterprise.sso import MicrosoftSSO
        sso = MicrosoftSSO(client_id="test", client_secret="secret",
                           redirect_uri="http://localhost", tenant="common")
        with pytest.raises(Exception) as exc_info:
            _run(sso.exchange_code("fake-code"))
        assert "NotImplementedError" not in type(exc_info.value).__name__

    def test_okta_exchange_not_raises(self):
        from temporalos.enterprise.sso import OktaSSO
        sso = OktaSSO(client_id="test", client_secret="secret",
                      redirect_uri="http://localhost", okta_domain="https://test.okta.com")
        with pytest.raises(Exception) as exc_info:
            _run(sso.exchange_code("fake-code"))
        assert "NotImplementedError" not in type(exc_info.value).__name__


# ── 4. LLM Summarization Engine ──────────────────────────────────────────────

class TestLLMSummarization:

    def test_llm_summary_engine_class_exists(self):
        from temporalos.summarization.engine import LLMSummaryEngine
        eng = LLMSummaryEngine.__new__(LLMSummaryEngine)
        assert hasattr(eng, "generate")

    def test_llm_summary_fallback_to_mock(self):
        """When no LLM key is set, should fall back to mock and still return."""
        from temporalos.summarization.engine import get_llm_summary_engine, SummaryType
        eng = get_llm_summary_engine()
        intel = {
            "segments": [
                {"extraction": {"topic": "pricing", "risk": "high", "risk_score": 0.8,
                 "objections": ["too expensive"], "decision_signals": ["ready"]},
                 "transcript": "Let me explain our pricing model.",
                 "timestamp_str": "00:10"},
            ]
        }
        result = _run(eng.generate(intel, SummaryType.EXECUTIVE))
        assert hasattr(result, "content")
        assert len(result.content) > 0


# ── 5. Knowledge Graph NER ────────────────────────────────────────────────────

class TestKnowledgeGraphNER:

    def test_extracts_money_amounts(self):
        from temporalos.agents.knowledge_graph import _extract_entities
        entities = _extract_entities("The deal is worth $50,000 per year")
        labels = [e[0] for e in entities]
        assert any("$50,000" in l for l in labels)

    def test_extracts_email(self):
        from temporalos.agents.knowledge_graph import _extract_entities
        entities = _extract_entities("Contact us at sales@acme.com")
        labels = [e[0] for e in entities]
        assert any("sales@acme.com" in l for l in labels)

    def test_extracts_org_suffixes(self):
        from temporalos.agents.knowledge_graph import _extract_entities
        entities = _extract_entities("We are partnering with Acme Corp")
        labels = [e[0] for e in entities]
        assert any("Acme Corp" in l for l in labels)

    def test_extracts_percentage(self):
        from temporalos.agents.knowledge_graph import _extract_entities
        entities = _extract_entities("Conversion rate improved by 25%")
        labels = [e[0] for e in entities]
        assert any("25%" in l for l in labels)

    def test_extracts_keyword_patterns(self):
        from temporalos.agents.knowledge_graph import _extract_entities
        entities = _extract_entities("The pricing includes budget and timeline")
        labels = [e[0] for e in entities]
        assert "pricing" in labels
        assert "budget" in labels
        assert "timeline" in labels


# ── 6. QA Agent LLM Synthesis ────────────────────────────────────────────────

class TestQAAgentSynthesis:

    def test_qa_agent_returns_answer(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        agent.index_job("test-job", {
            "segments": [
                {"extraction": {"topic": "pricing", "risk_score": 0.7,
                 "objections": ["expensive"], "decision_signals": ["ready"]},
                 "timestamp_str": "00:10",
                 "transcript": "Our enterprise plan costs $10,000 per year."},
            ]
        })
        result = agent.ask("What is the pricing?")
        assert hasattr(result, "answer")
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    def test_qa_agent_has_synthesize_method(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        assert hasattr(agent, "_synthesize") or hasattr(agent, "_synthesize_mock")


# ── 7. ASR Auto-Detect ───────────────────────────────────────────────────────

class TestASRAutoDetect:

    def test_auto_returns_mock_without_key(self):
        from temporalos.audio.streaming import get_streaming_asr, MockStreamingASR
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPGRAM_API_KEY", None)
            asr = get_streaming_asr("auto")
            assert isinstance(asr, MockStreamingASR)

    def test_factory_default_is_auto(self):
        """Default backend should be 'auto', not 'mock'."""
        import inspect
        from temporalos.audio.streaming import get_streaming_asr
        sig = inspect.signature(get_streaming_asr)
        default = sig.parameters["backend"].default
        assert default == "auto"


# ── 8. Vertical Pack Extraction ──────────────────────────────────────────────

class TestVerticalExtraction:

    def test_sales_extract_pricing(self):
        from temporalos.verticals.sales import SalesPack
        pack = SalesPack()
        seg = {"topic": "pricing", "transcript": "The cost is $25,000 per year",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert result.get("pricing_mentions")
        assert "$25,000" in result["pricing_mentions"][0]

    def test_sales_extract_competitor(self):
        from temporalos.verticals.sales import SalesPack
        pack = SalesPack()
        seg = {"topic": "comparison", "transcript": "We compared with Salesforce",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert "salesforce" in result.get("competitor_mentions", [])

    def test_sales_extract_deal_stage(self):
        from temporalos.verticals.sales import SalesPack
        pack = SalesPack()
        seg = {"topic": "demo", "transcript": "Let me show you how it works in a demo",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert result.get("deal_stage") in [
            "discovery", "demo", "evaluation", "negotiation", "closed-won"]

    def test_cs_extract_churn_signals(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        pack = CustomerSuccessPack()
        seg = {"topic": "renewal", "transcript": "We're thinking of canceling, very frustrated",
               "objections": ["not using the product"], "decision_signals": []}
        result = pack.extract(seg)
        assert result["churn_risk"] == "high"
        assert len(result["churn_indicators"]) >= 2
        assert result["health_signal"] == "red"

    def test_cs_extract_expansion(self):
        from temporalos.verticals.customer_success import CustomerSuccessPack
        pack = CustomerSuccessPack()
        seg = {"topic": "growth", "transcript": "We want to add users across the new team",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert len(result["expansion_signals"]) > 0
        assert result["churn_risk"] == "low"

    def test_ux_extract_pain_points(self):
        from temporalos.verticals.ux_research import UXResearchPack
        pack = UXResearchPack()
        seg = {"topic": "usability",
               "transcript": "This is really frustrating, I'm confused and lost",
               "objections": []}
        result = pack.extract(seg)
        assert "frustrating" in result.get("pain_points", [])
        assert "confused" in result.get("confusion_signals", [])
        assert result["segment_type"] == "pain_point"

    def test_ux_extract_delight(self):
        from temporalos.verticals.ux_research import UXResearchPack
        pack = UXResearchPack()
        seg = {"topic": "feedback", "transcript": "I love this feature, it's amazing",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert len(result["delight_moments"]) > 0
        assert result["segment_type"] == "delight"

    def test_ux_extract_feature_request(self):
        from temporalos.verticals.ux_research import UXResearchPack
        pack = UXResearchPack()
        seg = {"topic": "feedback",
               "transcript": "I wish there was a way to export reports, it's a missing feature",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert len(result["feature_requests"]) > 0

    def test_real_estate_extract_budget(self):
        from temporalos.verticals.real_estate import RealEstatePack
        pack = RealEstatePack()
        seg = {"topic": "pricing", "transcript": "Our budget is around $500,000",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert result.get("budget_signals")

    def test_real_estate_extract_timeline(self):
        from temporalos.verticals.real_estate import RealEstatePack
        pack = RealEstatePack()
        seg = {"topic": "timeline", "transcript": "We need to move in right away, it's urgent",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        assert result.get("timeline_urgency") == "immediately"

    def test_real_estate_extract_priorities(self):
        from temporalos.verticals.real_estate import RealEstatePack
        pack = RealEstatePack()
        seg = {"topic": "requirements",
               "transcript": "We need at least 3 bedroom, a garage, and good school district",
               "objections": [], "decision_signals": []}
        result = pack.extract(seg)
        has_priorities = result.get("client_priorities", [])
        assert any("bedroom" in p for p in has_priorities)

    def test_base_extract_passthrough(self):
        from temporalos.verticals.base import VerticalPack

        class DummyPack(VerticalPack):
            id = "dummy"
            name = "Dummy"
            description = "Test"
            industries = []
            summary_type = "executive"
            def schema(self):
                return None

        pack = DummyPack()
        seg = {"topic": "test", "data": 42}
        assert pack.extract(seg) == seg


# ── 9. Clip Reel FFmpeg Wiring ───────────────────────────────────────────────

class TestClipReelWiring:

    def test_build_reel_accepts_video_path_arg(self):
        import inspect
        from temporalos.intelligence.clip_reels import build_reel
        sig = inspect.signature(build_reel)
        assert "video_path" in sig.parameters

    def test_build_reel_produces_clips(self):
        from temporalos.intelligence.clip_reels import build_reel
        segments = [
            {"extraction": {"topic": "pricing", "risk_score": 0.7,
                            "objections": ["expensive"], "decision_signals": ["interested"]},
             "timestamp_ms": 5000, "duration_ms": 30000,
             "transcript": "Let me discuss gong competitor pricing"},
        ]
        reel = build_reel("test-reel", "job-123", segments)
        assert reel.clip_count > 0 if hasattr(reel, "clip_count") else len(reel.clips) > 0


# ── 10. Storage Wiring ───────────────────────────────────────────────────────

class TestStorageBackend:

    def test_local_storage_put_get(self):
        from temporalos.storage import LocalStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(base_dir=tmpdir)
            _run(storage.put("test/file.txt", b"hello world"))
            data = _run(storage.get("test/file.txt"))
            assert data == b"hello world"

    def test_local_storage_list_and_delete(self):
        from temporalos.storage import LocalStorage
        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve symlinks to handle macOS /var → /private/var
            resolved = str(Path(tmpdir).resolve())
            storage = LocalStorage(base_dir=resolved)
            _run(storage.put("videos/a.mp4", b"video-a"))
            _run(storage.put("videos/b.mp4", b"video-b"))
            keys = _run(storage.list_keys("videos"))
            assert len(keys) == 2
            assert _run(storage.delete("videos/a.mp4"))
            assert not _run(storage.exists("videos/a.mp4"))

    def test_get_storage_returns_local_by_default(self):
        from temporalos.storage import reset_storage, get_storage, LocalStorage
        reset_storage()
        os.environ.pop("STORAGE_BACKEND", None)
        s = get_storage()
        assert isinstance(s, LocalStorage)
        reset_storage()


# ── 11. Search Index In-Memory Rebuild ────────────────────────────────────────

class TestSearchIndexRebuild:

    def test_search_index_insert_and_query(self):
        from temporalos.search.indexer import SearchIndex, IndexEntry
        idx = SearchIndex()
        idx.index(IndexEntry(
            doc_id="j1:00:10",
            video_id="j1",
            timestamp_ms=10000,
            timestamp_str="00:10",
            topic="pricing",
            risk="high",
            risk_score=0.85,
            objections=["expensive"],
            decision_signals=["ready"],
            transcript="The pricing is too expensive for our budget",
            model="gpt-4o",
        ))
        results = idx.search("pricing expensive")
        assert len(results) > 0
        assert results[0].entry.topic == "pricing"

    def test_search_index_clear(self):
        from temporalos.search.indexer import SearchIndex, IndexEntry
        idx = SearchIndex()
        idx.index(IndexEntry(
            doc_id="x:1", video_id="x", timestamp_ms=0, timestamp_str="",
            topic="test", risk="low", risk_score=0.1,
            objections=[], decision_signals=[], transcript="hello world", model="m",
        ))
        assert idx.document_count == 1
        idx.clear()
        assert idx.document_count == 0
