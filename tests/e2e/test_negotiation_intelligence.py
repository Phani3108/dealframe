"""
Negotiation Intelligence end-to-end test.

Tests the game-theory and behavioral economics analysis layer:
  - Per-segment tactical analysis (BATNA, power balance, tactic detection)
  - Session-level strategic analysis (ZOPA, Nash equilibrium, concession patterns)
  - Integration with ProcurementPack.extract()
  - Anchor analysis and power shift tracking
  - Value-creation opportunity identification
  - Recommendation generation

Rules (from claude.md §0):
  - All real code; only external API calls are mocked
  - Asserts correct output schema and non-empty results
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from temporalos.intelligence.negotiation import (
    AnchorAnalysis,
    BATNAAssessment,
    ConcessionEvent,
    NashEquilibriumEstimate,
    NegotiationAnalyzer,
    PowerBalance,
    SegmentNegotiationIntel,
    SessionNegotiationReport,
    TacticDetection,
    ZOPAEstimate,
    enrich_segment_negotiation_intel,
    generate_session_report,
)
from temporalos.verticals.procurement import ProcurementPack


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def analyzer():
    return NegotiationAnalyzer()


@pytest.fixture
def buyer_segment_with_alternatives() -> Dict:
    """Buyer segment with strong BATNA and competing bids."""
    return {
        "topic": "pricing",
        "transcript": (
            "We have other suppliers quoting between $3.60 and $3.80. "
            "We also have a competing bid from an alternative vendor at $3.50. "
            "Our incumbent provider can match $3.70. At $4.20 you're above market. "
            "We need to decide by end of quarter. What flexibility do you have?"
        ),
        "objections": ["pricing too high", "above market"],
        "decision_signals": [],
        "speaker": "BUYER — Maria (Category Mgr)",
        "commitment_strength": "none",
        "concessions_offered": [],
    }


@pytest.fixture
def supplier_concession_segment() -> Dict:
    """Supplier making concessions with logrolling."""
    return {
        "topic": "pricing",
        "transcript": (
            "I understand the competitive landscape. We could go down to $3.85 at "
            "15,000 units with a two-year commitment. "
            "If you can do a multi-year deal, in exchange for the volume commitment "
            "we'll include DDP shipping and a dedicated storage allocation. "
            "We can do the sustainability certification at no extra cost. "
            "That's our best we can offer at this volume tier."
        ),
        "objections": [],
        "decision_signals": ["we could go down to"],
        "speaker": "SUPPLIER — James (Account Exec)",
        "commitment_strength": "weak",
        "concessions_offered": ["we could go down to", "we can do", "best we can offer"],
    }


@pytest.fixture
def escalation_segment() -> Dict:
    """Segment with escalation and walkaway signals."""
    return {
        "topic": "contract_terms",
        "transcript": (
            "This is unacceptable. We can't accept the auto-renewal clause. "
            "The limitation of liability cap is a deal breaker. "
            "Our legal team considers this a non-starter. "
            "If these terms don't change, we'll go elsewhere and take our business "
            "to another supplier. Walk away is on the table."
        ),
        "objections": ["auto-renewal", "liability cap"],
        "decision_signals": [],
        "speaker": "BUYER — Maria (Category Mgr)",
        "commitment_strength": "none",
        "concessions_offered": [],
    }


@pytest.fixture
def deescalation_segment() -> Dict:
    """Segment with de-escalation and collaborative signals."""
    return {
        "topic": "relationship",
        "transcript": (
            "I appreciate your flexibility on the pricing. Let's find a way "
            "to work together on the remaining terms. We're open to a "
            "long-term partnership and a multi-year strategic relationship. "
            "Collaboration on the ESG requirements would be a win-win. "
            "We understand your position and want to accommodate."
        ),
        "objections": [],
        "decision_signals": ["long-term partnership"],
        "speaker": "BUYER — Maria",
        "commitment_strength": "none",
        "concessions_offered": [],
    }


@pytest.fixture
def full_negotiation_session() -> List[Dict]:
    """Multi-segment negotiation session for session-level analysis."""
    return [
        {
            "topic": "pricing",
            "transcript": (
                "Your pricing came in at $4.20 per unit for the RA-500 line. "
                "Our standard volume pricing at 10,000 units per quarter."
            ),
            "objections": [],
            "decision_signals": [],
            "speaker": "SUPPLIER — James (Account Exec)",
            "commitment_strength": "none",
            "concessions_offered": [],
        },
        {
            "topic": "pricing",
            "transcript": (
                "We have other suppliers quoting between $3.60 and $3.80. "
                "At $4.20 you're above market. Several bidders are in the range."
            ),
            "objections": ["pricing too high"],
            "decision_signals": [],
            "speaker": "BUYER — Maria (Category Mgr)",
            "commitment_strength": "none",
            "concessions_offered": [],
        },
        {
            "topic": "pricing",
            "transcript": (
                "We could go down to $3.85 at 15,000 units with a two-year commitment. "
                "We can do the sustainability certification at no extra cost. "
                "That's our best we can offer."
            ),
            "objections": [],
            "decision_signals": [],
            "speaker": "SUPPLIER — James",
            "commitment_strength": "weak",
            "concessions_offered": ["we could go down to", "we can do", "best we can offer"],
        },
        {
            "topic": "delivery",
            "transcript": (
                "Your lead times last quarter averaged 18 days versus the 12-day SLA. "
                "We can confirm 10-day lead times with a 99.5% on-time delivery KPI. "
                "We will include a penalty clause."
            ),
            "objections": ["lead time miss"],
            "decision_signals": ["we can confirm"],
            "speaker": "SUPPLIER — James",
            "commitment_strength": "strong",
            "concessions_offered": [],
        },
        {
            "topic": "contract_terms",
            "transcript": (
                "We can't accept the auto-renewal clause or the limitation of liability. "
                "We could consider removing auto-renewal. Let me check with legal."
            ),
            "objections": ["auto-renewal", "liability cap"],
            "decision_signals": [],
            "speaker": "BUYER — Maria",
            "commitment_strength": "weak",
            "concessions_offered": ["we could consider"],
        },
        {
            "topic": "compliance",
            "transcript": (
                "We need ISO 14001 and your carbon footprint audit by Q3. "
                "ISO 14001 is confirmed. Carbon audit is in progress. We guarantee delivery."
            ),
            "objections": [],
            "decision_signals": ["confirmed"],
            "speaker": "SUPPLIER — James",
            "commitment_strength": "strong",
            "concessions_offered": [],
        },
        {
            "topic": "pricing",
            "transcript": (
                "I need the total cost picture — shipping, storage, and integration cost. "
                "Total cost of ownership should drop below $4.10 all-in at 20,000 units. "
                "If you can lock in $3.85 per unit we have a deal. Agreed."
            ),
            "objections": [],
            "decision_signals": ["we have a deal", "agreed"],
            "speaker": "BUYER — Maria",
            "commitment_strength": "strong",
            "concessions_offered": [],
        },
    ]


# ── Per-Segment Tactic Detection ─────────────────────────────────────────────

class TestTacticDetection:
    """Test detection of negotiation tactics in individual segments."""

    def test_anchoring_detected(self, analyzer):
        seg = {
            "transcript": "Our standard price is $4.20 per unit. "
                          "That's our starting point for this volume.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "anchoring" in tactic_names

    def test_time_pressure_detected(self, analyzer):
        seg = {
            "transcript": "We need to decide by end of quarter. "
                          "This offer expires Friday. The window is closing.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "time_pressure" in tactic_names

    def test_walkaway_threat_detected(self, analyzer, escalation_segment):
        intel = analyzer.analyze_segment(escalation_segment)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "walkaway_threat" in tactic_names

    def test_logrolling_detected(self, analyzer, supplier_concession_segment):
        intel = analyzer.analyze_segment(supplier_concession_segment)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "logrolling" in tactic_names

    def test_good_cop_bad_cop_detected(self, analyzer):
        seg = {
            "transcript": "I want to help but my manager won't approve those terms. "
                          "Let me escalate this to get better pricing. My hands are tied.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "good_cop_bad_cop" in tactic_names

    def test_nibbling_detected(self, analyzer):
        seg = {
            "transcript": "Great, we have a deal. By the way, could you also "
                          "throw in the training program? Just one more small addition.",
            "objections": [], "decision_signals": [], "topic": "relationship",
        }
        intel = analyzer.analyze_segment(seg)
        tactic_names = [t.tactic for t in intel.tactics_detected]
        assert "nibbling" in tactic_names

    def test_no_false_positives_on_clean_text(self, analyzer):
        seg = {
            "transcript": "The weather is nice today. Let's review the agenda.",
            "objections": [], "decision_signals": [], "topic": "general",
        }
        intel = analyzer.analyze_segment(seg)
        assert len(intel.tactics_detected) == 0

    def test_tactic_confidence_scales(self, analyzer):
        seg = {
            "transcript": "Need to decide by end of quarter. Deadline is Friday. "
                          "Window is closing. Offer expires tomorrow. Limited time.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        time_pressure = next(
            (t for t in intel.tactics_detected if t.tactic == "time_pressure"), None
        )
        assert time_pressure is not None
        assert time_pressure.confidence >= 0.67  # 2+ keywords


# ── BATNA Assessment ─────────────────────────────────────────────────────────

class TestBATNAAssessment:
    """Test Best Alternative to Negotiated Agreement signal detection."""

    def test_buyer_batna_strong(self, analyzer, buyer_segment_with_alternatives):
        intel = analyzer.analyze_segment(buyer_segment_with_alternatives)
        assert intel.batna.buyer_batna_strength in ("strong", "moderate")
        assert len(intel.batna.buyer_batna_signals) >= 2

    def test_supplier_batna_detected(self, analyzer):
        seg = {
            "transcript": "We have high demand for this product. Limited capacity "
                          "means allocation is tight. Other customers are waiting.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.batna.supplier_batna_strength != "none"
        assert len(intel.batna.supplier_batna_signals) >= 1

    def test_no_batna_on_neutral_text(self, analyzer):
        seg = {
            "transcript": "Let's review the specification requirements.",
            "objections": [], "decision_signals": [], "topic": "quality",
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.batna.buyer_batna_strength == "none"
        assert intel.batna.supplier_batna_strength == "none"


# ── Power Balance ────────────────────────────────────────────────────────────

class TestPowerBalance:
    """Test buyer/supplier leverage estimation."""

    def test_buyer_leverage_with_alternatives(self, analyzer, buyer_segment_with_alternatives):
        intel = analyzer.analyze_segment(buyer_segment_with_alternatives)
        assert intel.power_balance.buyer_leverage > intel.power_balance.supplier_leverage
        assert intel.power_balance.dominant_party == "buyer"

    def test_supplier_leverage_with_scarcity(self, analyzer):
        seg = {
            "transcript": "This is a sole source product. No one else offers "
                          "this formulation. We have high demand and limited capacity. "
                          "Proprietary technology.",
            "objections": [], "decision_signals": [], "topic": "pricing",
            "commitment_strength": "strong",
            "concessions_offered": [],
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.power_balance.supplier_leverage > intel.power_balance.buyer_leverage
        assert intel.power_balance.dominant_party == "supplier"

    def test_balanced_power(self, analyzer):
        seg = {
            "transcript": "Let's discuss the standard terms.",
            "objections": [], "decision_signals": [], "topic": "general",
            "commitment_strength": "none", "concessions_offered": [],
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.power_balance.dominant_party == "balanced"

    def test_leverage_drivers_populated(self, analyzer, buyer_segment_with_alternatives):
        intel = analyzer.analyze_segment(buyer_segment_with_alternatives)
        assert len(intel.power_balance.leverage_drivers) >= 1


# ── Escalation / De-escalation ───────────────────────────────────────────────

class TestEscalation:
    """Test escalation and de-escalation detection."""

    def test_escalation_detected(self, analyzer, escalation_segment):
        intel = analyzer.analyze_segment(escalation_segment)
        assert intel.escalation_level == "escalating"

    def test_deescalation_detected(self, analyzer, deescalation_segment):
        intel = analyzer.analyze_segment(deescalation_segment)
        assert intel.escalation_level == "de_escalating"

    def test_stable_on_neutral(self, analyzer):
        seg = {
            "transcript": "Let's review the delivery schedule for next quarter.",
            "objections": [], "decision_signals": [], "topic": "delivery",
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.escalation_level == "stable"


# ── Bargaining Style ────────────────────────────────────────────────────────

class TestBargainingStyle:
    """Test integrative vs. distributive bargaining classification."""

    def test_integrative_detected(self, analyzer, deescalation_segment):
        intel = analyzer.analyze_segment(deescalation_segment)
        assert intel.bargaining_style == "integrative"

    def test_distributive_detected(self, analyzer):
        seg = {
            "transcript": "This is our final offer. Take it or leave it. "
                          "The price is non-negotiable. Bottom line.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.bargaining_style == "distributive"

    def test_mixed_style(self, analyzer):
        seg = {
            "transcript": "We can bundle a package deal for mutual benefit "
                          "but the core price is our bottom line.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        assert intel.bargaining_style in ("integrative", "mixed")


# ── Issue Detection ──────────────────────────────────────────────────────────

class TestIssueDetection:
    """Test multi-issue identification."""

    def test_price_and_delivery_detected(self, analyzer):
        seg = {
            "transcript": "The per unit cost is $3.85 with 10-day lead time "
                          "and DDP shipping.",
            "objections": [], "decision_signals": [], "topic": "pricing",
        }
        intel = analyzer.analyze_segment(seg)
        assert "price" in intel.issues_on_table
        assert "delivery" in intel.issues_on_table

    def test_contract_and_compliance(self, analyzer):
        seg = {
            "transcript": "The auto-renewal clause needs to change. "
                          "ISO certification and ESG audit are required.",
            "objections": [], "decision_signals": [], "topic": "contract_terms",
        }
        intel = analyzer.analyze_segment(seg)
        assert "contract_terms" in intel.issues_on_table
        assert "compliance" in intel.issues_on_table


# ── Session-Level Analysis ───────────────────────────────────────────────────

class TestSessionAnalysis:
    """Test session-level strategic analysis across multiple segments."""

    def test_session_report_structure(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        assert isinstance(report, SessionNegotiationReport)
        assert report.zopa is not None
        assert report.nash_equilibrium is not None
        assert isinstance(report.concession_trajectory, list)
        assert isinstance(report.power_shift_timeline, list)
        assert report.deal_health in ("converging", "stalled", "diverging")
        assert isinstance(report.recommended_moves, list)

    def test_zopa_estimation(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        # Session has buyer mentioning $3.60-$3.80 range, supplier at $4.20→$3.85
        zopa = report.zopa
        assert zopa.buyer_ceiling is not None
        assert zopa.supplier_floor is not None

    def test_nash_equilibrium_estimated(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        nash = report.nash_equilibrium
        # Should produce an estimate given the price data
        assert nash.method != "insufficient_data"
        if nash.estimated_agreement_point is not None:
            assert nash.estimated_agreement_point > 0

    def test_anchor_analysis(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        anchor = report.anchor_analysis
        assert anchor is not None
        assert anchor.anchor_price > 0
        # First mentioned price in session is $4.20
        assert anchor.anchor_price == 4.20

    def test_concession_trajectory_tracked(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        # Session has concessions in segment 2 (supplier) and segment 4 (buyer)
        assert len(report.concession_trajectory) >= 1

    def test_power_shift_timeline(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        assert len(report.power_shift_timeline) == len(full_negotiation_session)
        for entry in report.power_shift_timeline:
            assert "segment" in entry
            assert "buyer_leverage" in entry
            assert "supplier_leverage" in entry

    def test_deal_health_converging(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        # Session ends with "we have a deal" / "agreed" — should be converging
        assert report.deal_health == "converging"

    def test_issues_tracking(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        all_issues = set(report.issues_resolved + report.issues_open)
        assert len(all_issues) >= 1

    def test_value_creation_opportunities(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        # Session discusses price + delivery + compliance — should trigger opportunities
        assert len(report.value_creation_opportunities) >= 1

    def test_recommendations_generated(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        assert len(report.recommended_moves) >= 1

    def test_tactics_summary(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        assert isinstance(report.overall_tactics_summary, dict)

    def test_session_report_to_dict(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "zopa" in d
        assert "nash_equilibrium" in d
        assert "deal_health" in d
        assert "recommended_moves" in d


# ── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    """Test the convenience functions for segment and session enrichment."""

    def test_enrich_segment(self):
        seg = {
            "topic": "pricing",
            "transcript": "We have other suppliers quoting lower. "
                          "This is our final offer at $3.85. Take it or leave it.",
            "objections": ["price too high"],
            "decision_signals": [],
            "speaker": "BUYER — Maria",
            "commitment_strength": "none",
            "concessions_offered": [],
        }
        result = enrich_segment_negotiation_intel(seg)
        assert "negotiation_tactics" in result
        assert "power_balance" in result
        assert "batna_assessment" in result
        assert "escalation_level" in result
        assert "bargaining_style" in result
        assert "issues_on_table" in result

    def test_enrich_segment_empty_transcript(self):
        seg = {
            "topic": "general",
            "transcript": "",
            "objections": [],
            "decision_signals": [],
        }
        result = enrich_segment_negotiation_intel(seg)
        assert result["escalation_level"] == "stable"
        assert result["bargaining_style"] == "mixed"
        assert len(result["negotiation_tactics"]) == 0

    def test_generate_session_report(self, full_negotiation_session):
        report_dict = generate_session_report(full_negotiation_session)
        assert isinstance(report_dict, dict)
        assert "zopa" in report_dict
        assert "nash_equilibrium" in report_dict
        assert "concession_pattern" in report_dict


# ── Integration with ProcurementPack ─────────────────────────────────────────

class TestProcurementPackIntegration:
    """Test that ProcurementPack.extract() now includes negotiation intelligence."""

    def test_extract_includes_negotiation_fields(self):
        pack = ProcurementPack()
        seg = {
            "topic": "pricing",
            "transcript": (
                "We have other suppliers quoting $3.60. "
                "We could go down to $3.85. We can do a volume discount. "
                "If you handle shipping, we can agree on the per-unit price. "
                "Let's find a way to work together — a long-term partnership. "
                "Our SLA requires 10-day lead times."
            ),
            "objections": [],
            "decision_signals": [],
            "speaker": "SUPPLIER — James",
        }
        result = pack.extract(seg)

        # Original procurement fields
        assert "pricing_signals" in result
        assert "concessions_offered" in result
        assert "commitment_strength" in result

        # New negotiation intelligence fields
        assert "negotiation_tactics" in result
        assert "power_balance" in result
        assert "batna_assessment" in result
        assert "escalation_level" in result
        assert "bargaining_style" in result
        assert "issues_on_table" in result

    def test_power_balance_structure(self):
        pack = ProcurementPack()
        seg = {
            "topic": "pricing",
            "transcript": "Other suppliers have competing bids. We have options.",
            "objections": [],
            "decision_signals": [],
            "speaker": "BUYER — Maria",
        }
        result = pack.extract(seg)
        pb = result["power_balance"]
        assert "buyer_leverage" in pb
        assert "supplier_leverage" in pb
        assert "dominant_party" in pb
        assert isinstance(pb["buyer_leverage"], float)

    def test_schema_includes_game_theory_fields(self):
        pack = ProcurementPack()
        schema = pack.schema()
        field_names = [f.name for f in schema.fields]
        game_theory_fields = [
            "negotiation_tactics", "power_balance", "batna_assessment",
            "escalation_level", "bargaining_style", "issues_on_table",
            "integrative_signals",
        ]
        for f in game_theory_fields:
            assert f in field_names, f"Missing game theory field: {f}"

    def test_field_count_increased(self):
        pack = ProcurementPack()
        schema = pack.schema()
        assert len(schema.fields) >= 25, (
            f"Expected 25+ fields with game theory additions, got {len(schema.fields)}"
        )


# ── Edge Cases & Robustness ──────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and robustness of the analyzer."""

    def test_single_segment_session(self, analyzer):
        segments = [{
            "topic": "general",
            "transcript": "Hello, let's begin.",
            "objections": [], "decision_signals": [],
        }]
        report = analyzer.analyze_session(segments)
        assert report.deal_health == "converging"
        assert report.concession_pattern == "none"

    def test_empty_session(self, analyzer):
        report = analyzer.analyze_session([])
        assert report.deal_health == "converging"
        assert report.concession_pattern == "none"
        assert report.zopa.confidence == "low"

    def test_session_with_no_prices(self, analyzer):
        segments = [
            {"topic": "quality", "transcript": "Let's discuss specifications.",
             "objections": [], "decision_signals": []},
            {"topic": "compliance", "transcript": "ISO certification is mandatory.",
             "objections": [], "decision_signals": []},
        ]
        report = analyzer.analyze_session(segments)
        assert report.anchor_analysis is None
        assert report.nash_equilibrium.method == "insufficient_data"

    def test_diverging_negotiation(self, analyzer):
        segments = [
            {"topic": "pricing",
             "transcript": "This is unacceptable. Deal breaker. Walk away. Non-starter.",
             "objections": ["everything"], "decision_signals": []},
            {"topic": "contract_terms",
             "transcript": "Not acceptable. The consequences will be severe. Breach of trust.",
             "objections": ["all terms"], "decision_signals": []},
            {"topic": "pricing",
             "transcript": "We'll go elsewhere. Take our business to another supplier. No deal.",
             "objections": ["everything"], "decision_signals": []},
        ]
        report = analyzer.analyze_session(segments)
        assert report.deal_health == "diverging"

    def test_all_data_classes_serializable(self, analyzer, full_negotiation_session):
        report = analyzer.analyze_session(full_negotiation_session)
        d = report.to_dict()
        # Verify entire dict is JSON-serializable
        import json
        json_str = json.dumps(d)
        assert len(json_str) > 100
        parsed = json.loads(json_str)
        assert "zopa" in parsed
