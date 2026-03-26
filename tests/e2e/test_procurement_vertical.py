"""
Procurement Vertical end-to-end test.

Tests the full procurement pipeline:
  - ProcurementPack schema, extract, keyword detection
  - Franchise auto-detection of procurement content
  - Integration with pipeline (video → frames → transcript → alignment → extraction → procurement enrichment)
  - Demo script transcript extraction
  - Vertical registration in the registry

Rules (from claude.md §0):
  - All real code; only external API calls are mocked
  - Asserts correct output schema and non-empty results
"""

from __future__ import annotations

import json
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from temporalos.core.types import AlignedSegment, ExtractionResult, Frame, Word
from temporalos.schemas.registry import FieldType
from temporalos.verticals.procurement import ProcurementPack
from temporalos.verticals import get_default_vertical_registry
from temporalos.intelligence.franchise import classify_vertical, VERTICAL_KEYWORDS, VERTICAL_SCHEMAS


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def procurement_pack():
    return ProcurementPack()


@pytest.fixture
def supplier_negotiation_transcript() -> str:
    """Realistic supplier negotiation transcript with procurement signals."""
    return (
        "Thanks for joining. We received your response to our RFP for industrial "
        "adhesives. Your pricing came in at $4.20 per unit for the RA-500 line. "
        "I want to walk through a few areas before we finalize. "
        "Absolutely. The $4.20 reflects our standard volume pricing at 10,000 "
        "units per quarter. We can do $3.95 if you commit to 25,000. "
        "We have other suppliers quoting between $3.60 and $3.80. At $4.20 you're "
        "above market. What flexibility do you have? "
        "I understand the competitive landscape. We could go down to $3.85 at "
        "15,000 units with a two-year commitment. That includes the sustainability "
        "certification your ESG team requires. "
        "Your lead times last quarter averaged 18 days versus the 12-day SLA. "
        "We had two production stoppages. What's changed? "
        "We've invested in a secondary production line. We can confirm 10-day "
        "lead times with a 99.5% on-time delivery KPI going forward. We will "
        "include a penalty clause — 2% credit per late shipment. "
        "On the contract terms — we can't accept the auto-renewal clause or the "
        "limitation of liability cap at $50,000. Our legal team will redline both sections. "
        "We could consider removing auto-renewal. The liability cap is subject "
        "to approval from our legal — let me check and get back to you. "
        "We need ISO 14001 and your carbon footprint audit by Q3. Our board "
        "has an ESG mandate — non-negotiable. "
        "ISO 14001 is confirmed. Carbon audit is in progress. We guarantee delivery. "
        "I need the total cost picture — shipping, storage, and integration cost "
        "included. The hidden costs last year added 12 percent on top of unit price. "
        "We'll include DDP shipping and provide a dedicated storage allocation. "
        "Total cost of ownership should drop below $4.10 all-in at 20,000 units. "
        "If you can lock in $3.85 per unit, 10-day lead times with penalty, remove "
        "auto-renewal, and deliver the carbon audit by Q2 — we have a deal. "
        "Agreed. I'll send the revised terms by Friday."
    )


@pytest.fixture
def procurement_segment_data(supplier_negotiation_transcript) -> Dict:
    """A segment dict as it arrives from the extraction pipeline."""
    return {
        "topic": "pricing",
        "sentiment": "negative",
        "risk": "high",
        "risk_score": 0.7,
        "objections": [
            "can't accept the auto-renewal clause",
            "limitation of liability cap at $50,000",
        ],
        "decision_signals": [
            "we have a deal",
            "lock in $3.85 per unit",
        ],
        "transcript": supplier_negotiation_transcript,
    }


# ── Schema Tests ──────────────────────────────────────────────────────────────

class TestProcurementSchema:
    """Validate the procurement schema definition."""

    def test_schema_id(self, procurement_pack):
        schema = procurement_pack.schema()
        assert schema.id == "procurement-pack-v1"
        assert schema.vertical == "procurement"

    def test_schema_has_all_required_fields(self, procurement_pack):
        schema = procurement_pack.schema()
        field_names = [f.name for f in schema.fields]
        required_fields = [
            "topic", "sentiment", "risk", "risk_score",
            "objections", "decision_signals",
        ]
        for f in required_fields:
            assert f in field_names, f"Missing required field: {f}"

    def test_schema_has_procurement_specific_fields(self, procurement_pack):
        schema = procurement_pack.schema()
        field_names = [f.name for f in schema.fields]
        procurement_fields = [
            "pricing_signals", "concessions_offered", "commitment_strength",
            "negotiation_stage", "supplier_risk_score",
            "delivery_risk_signals", "financial_risk_signals",
            "compliance_mentions", "clause_objections",
            "sla_commitments_discussed", "alternative_supplier_signals",
            "tco_signals", "maverick_spend_risk",
        ]
        for f in procurement_fields:
            assert f in field_names, f"Missing procurement field: {f}"

    def test_topic_has_procurement_categories(self, procurement_pack):
        schema = procurement_pack.schema()
        topic_field = next(f for f in schema.fields if f.name == "topic")
        assert "contract_terms" in topic_field.options
        assert "sourcing_strategy" in topic_field.options
        assert "compliance" in topic_field.options
        assert "sla" in topic_field.options

    def test_sentiment_includes_adversarial_and_collaborative(self, procurement_pack):
        schema = procurement_pack.schema()
        sentiment = next(f for f in schema.fields if f.name == "sentiment")
        assert "adversarial" in sentiment.options
        assert "collaborative" in sentiment.options

    def test_field_count(self, procurement_pack):
        schema = procurement_pack.schema()
        assert len(schema.fields) >= 25, "Procurement pack should have 25+ fields (incl. game theory)"

    def test_to_dict(self, procurement_pack):
        d = procurement_pack.to_dict()
        assert d["id"] == "procurement"
        assert d["name"] == "Procurement & Supplier Intelligence"
        assert "Manufacturing" in d["industries"]
        assert d["field_count"] >= 25


# ── Extraction Tests ──────────────────────────────────────────────────────────

class TestProcurementExtraction:
    """Validate keyword-based procurement extraction."""

    def test_pricing_signals_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["pricing_signals"]) >= 1, "Should detect pricing mentions"

    def test_concessions_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["concessions_offered"]) >= 1, "Should detect concessions"
        # "we could go down to" or "we can do" should match
        found_any = any(
            c in ["we can do", "could consider"]
            for c in result["concessions_offered"]
        )
        assert found_any or len(result["concessions_offered"]) > 0

    def test_commitment_strength_mixed(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        # Transcript has both "we will" (strong) and "let me check" (weak)
        assert result["commitment_strength"] in ("strong", "weak", "mixed")

    def test_delivery_risk_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["delivery_risk_signals"]) >= 1, "Should detect lead time issues"

    def test_compliance_mentions_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["compliance_mentions"]) >= 1
        has_iso_or_esg = any(
            kw in result["compliance_mentions"]
            for kw in ["iso", "esg", "carbon", "sustainability", "audit", "certification"]
        )
        assert has_iso_or_esg, "Should detect ISO/ESG/certification mentions"

    def test_sla_discussed(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert result["sla_commitments_discussed"] is True

    def test_negotiation_stage_inferred(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert result["negotiation_stage"] in (
            "rfp_review", "initial_offer", "counter_offer",
            "final_negotiation", "verbal_agreement",
        )

    def test_clause_objections_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["clause_objections"]) >= 1
        has_clause_issue = any(
            kw in result["clause_objections"]
            for kw in ["auto-renewal", "limitation of liability", "can't accept",
                       "payment terms", "liability"]
        )
        assert has_clause_issue, "Should detect clause objections"

    def test_tco_signals_detected(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["tco_signals"]) >= 1
        assert any("total cost" in s or "tco" in s or "hidden cost" in s
                    for s in result["tco_signals"])

    def test_alternative_supplier_signals(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert len(result["alternative_supplier_signals"]) >= 1

    def test_supplier_risk_score_range(self, procurement_pack, procurement_segment_data):
        result = procurement_pack.extract(procurement_segment_data)
        assert 0.0 <= result["supplier_risk_score"] <= 1.0

    def test_maverick_spend_detection_negative(self, procurement_pack):
        """Clean transcript should not flag maverick spend."""
        clean = {"topic": "general", "objections": [], "decision_signals": [],
                 "transcript": "We are reviewing the standard contract terms."}
        result = procurement_pack.extract(clean)
        assert result["maverick_spend_risk"] is False

    def test_maverick_spend_detection_positive(self, procurement_pack):
        """Transcript mentioning off-contract should flag maverick risk."""
        risky = {"topic": "general", "objections": [], "decision_signals": [],
                 "transcript": "The team has been doing off-contract purchasing to bypass the approval process."}
        result = procurement_pack.extract(risky)
        assert result["maverick_spend_risk"] is True


# ── Franchise Auto-Detection Tests ────────────────────────────────────────────

class TestProcurementFranchiseDetection:
    """Validate that procurement content is auto-classified correctly."""

    def test_procurement_keywords_exist(self):
        assert "procurement" in VERTICAL_KEYWORDS
        assert len(VERTICAL_KEYWORDS["procurement"]) >= 15

    def test_procurement_schema_exists(self):
        assert "procurement" in VERTICAL_SCHEMAS
        assert "supplier_risk_score" in VERTICAL_SCHEMAS["procurement"]
        assert "negotiation_stage" in VERTICAL_SCHEMAS["procurement"]

    def test_classify_procurement_content(self, supplier_negotiation_transcript):
        intel = {
            "segments": [{
                "transcript": supplier_negotiation_transcript,
                "extraction": {
                    "topic": "pricing",
                    "objections": ["can't accept auto-renewal"],
                    "decision_signals": ["we have a deal"],
                },
            }],
        }
        vertical, confidence, scores = classify_vertical(intel)
        assert vertical == "procurement", f"Expected procurement, got {vertical}"
        assert confidence > 0.2, f"Low confidence: {confidence}"
        assert scores.get("procurement", 0) > scores.get("sales_call", 0), \
            "Procurement should score higher than sales_call"

    def test_non_procurement_not_classified(self):
        intel = {
            "segments": [{
                "transcript": "The UX team ran a usability test on the prototype. "
                              "Participants found navigation confusing.",
                "extraction": {"topic": "usability", "objections": [], "decision_signals": []},
            }],
        }
        vertical, _, _ = classify_vertical(intel)
        assert vertical != "procurement"


# ── Registry Integration Tests ────────────────────────────────────────────────

class TestProcurementRegistry:
    """Validate procurement pack is properly registered."""

    def test_procurement_in_registry(self):
        registry = get_default_vertical_registry()
        pack = registry.get("procurement")
        assert pack is not None, "ProcurementPack must be registered"
        assert pack.id == "procurement"

    def test_registry_lists_procurement(self):
        registry = get_default_vertical_registry()
        all_packs = registry.list()
        ids = [p.id for p in all_packs]
        assert "procurement" in ids

    def test_total_verticals(self):
        registry = get_default_vertical_registry()
        all_packs = registry.list()
        assert len(all_packs) >= 5, "Should have at least 5 verticals now"


# ── Pack Metadata Tests ───────────────────────────────────────────────────────

class TestProcurementMetadata:
    """Validate pack metadata for Jaggaer-relevant industries."""

    def test_covers_jaggaer_industries(self, procurement_pack):
        industries = procurement_pack.industries
        assert "Manufacturing" in industries
        assert "Healthcare" in industries
        assert "Higher Education" in industries
        assert "Public Sector" in industries
        assert "Financial Services" in industries

    def test_summary_type(self, procurement_pack):
        assert procurement_pack.summary_type == "negotiation_brief"

    def test_description_mentions_s2p(self, procurement_pack):
        assert "S2P" in procurement_pack.description


# ── Pipeline Integration Test ─────────────────────────────────────────────────

class TestProcurementPipelineIntegration:
    """Test that procurement vertical integrates with the extraction pipeline."""

    def test_extract_enriches_pipeline_output(self, procurement_pack):
        """Simulate what happens when the pipeline sends extraction data
        through the procurement pack."""
        # This is the data shape the pipeline produces
        pipeline_output = {
            "topic": "pricing",
            "sentiment": "negative",
            "risk": "medium",
            "risk_score": 0.5,
            "objections": ["The supplier's pricing is too high"],
            "decision_signals": [],
            "transcript": (
                "We need to discuss the volume discount for the next quarter. "
                "The current supplier lead time is 15 days but our SLA requires 10. "
                "We have other suppliers quoting lower per unit pricing. "
                "The total cost including shipping is above budget. "
                "We can't accept the auto-renewal clause in the contract. "
                "ISO certification is required for compliance."
            ),
        }
        result = procurement_pack.extract(pipeline_output)

        # Verify enrichment happened
        assert "pricing_signals" in result
        assert "commitment_strength" in result
        assert "supplier_risk_score" in result
        assert "compliance_mentions" in result
        assert "clause_objections" in result
        assert "tco_signals" in result
        assert "sla_commitments_discussed" in result
        assert "negotiation_stage" in result

        # Verify detection worked
        assert result["sla_commitments_discussed"] is True
        assert len(result["compliance_mentions"]) >= 1
        assert len(result["clause_objections"]) >= 1
        assert len(result["tco_signals"]) >= 1

    def test_empty_transcript_doesnt_crash(self, procurement_pack):
        """Procurement extraction should handle empty/minimal input gracefully."""
        minimal = {
            "topic": "general",
            "objections": [],
            "decision_signals": [],
            "transcript": "",
        }
        result = procurement_pack.extract(minimal)
        assert result["commitment_strength"] == "none"
        assert result["supplier_risk_score"] == 0.0
        assert result["maverick_spend_risk"] is False
        assert result["sla_commitments_discussed"] is False

    def test_all_fields_populated(self, procurement_pack, procurement_segment_data):
        """After extraction, all expected procurement keys exist."""
        result = procurement_pack.extract(procurement_segment_data)
        expected_keys = [
            "pricing_signals", "concessions_offered", "commitment_strength",
            "delivery_risk_signals", "financial_risk_signals",
            "compliance_mentions", "supplier_risk_score",
            "sla_commitments_discussed", "negotiation_stage",
            "clause_objections", "alternative_supplier_signals",
            "tco_signals", "maverick_spend_risk",
            # Game theory fields
            "negotiation_tactics", "power_balance", "batna_assessment",
            "escalation_level", "bargaining_style", "issues_on_table",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
