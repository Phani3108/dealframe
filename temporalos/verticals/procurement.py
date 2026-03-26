"""Procurement & Supplier Negotiation Intelligence vertical pack.

Extracts structured negotiation intelligence from supplier calls, sourcing
committee reviews, contract negotiations, QBRs, and RFP presentations.
Designed to feed data into Source-to-Pay platforms (Jaggaer, Coupa, SAP Ariba).
"""
from __future__ import annotations

import re
from typing import Dict, List

from temporalos.intelligence.negotiation import enrich_segment_negotiation_intel
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack

# ---------------------------------------------------------------------------
# Keyword / regex constants
# ---------------------------------------------------------------------------

_PRICING_RE = re.compile(
    r"\$[\d,]+(?:\.\d{2})?(?:\s*[KkMmBb])?"
    r"|\d+(?:,\d{3})*\s*(?:dollars?|per\s+unit|per\s+piece|per\s+item)"
    r"|\d+(?:\.\d+)?\s*(?:percent|%)\s*(?:discount|off|reduction|savings?)",
    re.I,
)

_CONCESSION_KEYWORDS = frozenset({
    "we can do", "best we can offer", "we could go down to", "meet you halfway",
    "willing to reduce", "throw in", "include at no", "waive the fee",
    "take it or leave", "final offer", "as a gesture", "one-time credit",
    "volume discount", "early payment discount", "rebate",
})

_COMMITMENT_STRONG = frozenset({
    "we will", "we guarantee", "we commit", "that is confirmed",
    "you have our word", "absolutely", "without question",
    "we can confirm", "locked in", "agreed",
})

_COMMITMENT_WEAK = frozenset({
    "we could consider", "we might be able", "let me check",
    "i'll get back to you", "we'll see", "possibly", "potentially",
    "no promises", "subject to", "pending approval", "tentatively",
})

_DELIVERY_RISK_KEYWORDS = frozenset({
    "capacity issues", "lead time", "backorder", "supply shortage",
    "allocation", "force majeure", "delayed", "out of stock",
    "production constraint", "raw material", "shipping delay",
    "port congestion", "logistics challenge",
})

_FINANCIAL_RISK_KEYWORDS = frozenset({
    "cash flow", "restructuring", "layoff", "downsizing", "acquisition",
    "bankruptcy", "credit rating", "financial difficulty", "cost cutting",
    "budget freeze", "headcount reduction",
})

_COMPLIANCE_KEYWORDS = frozenset({
    "iso", "soc 2", "gdpr", "hipaa", "environmental", "carbon",
    "sustainability", "audit", "certification", "labor practice",
    "child labor", "conflict mineral", "modern slavery", "esg",
    "diversity", "ethical sourcing", "regulatory",
})

_SLA_KEYWORDS = frozenset({
    "service level", "sla", "uptime", "response time", "resolution time",
    "availability", "99.9", "penalty", "credit", "performance guarantee",
    "kpi", "metric", "benchmark",
})

_NEGOTIATION_STAGE_SIGNALS = {
    "rfp_review": {"rfp", "request for proposal", "bid", "tender", "submission",
                   "evaluation criteria", "scoring", "shortlist"},
    "initial_offer": {"initial offer", "first proposal", "opening position",
                      "starting point", "indicative pricing", "ballpark"},
    "counter_offer": {"counter", "revised offer", "new terms", "adjusted pricing",
                      "alternative proposal", "come back with"},
    "final_negotiation": {"final terms", "best and final", "bafo", "last offer",
                          "walk away", "deal breaker", "showstopper", "non-negotiable"},
    "verbal_agreement": {"agreed", "handshake", "we have a deal", "move forward",
                         "start the contract", "ready to sign", "proceed"},
}

_COMPETITOR_SUPPLIER_KEYWORDS = frozenset({
    "other supplier", "alternative vendor", "competing bid", "other quote",
    "incumbent", "current provider", "switch", "migrate", "replacement",
})

_TCO_KEYWORDS = frozenset({
    "total cost", "tco", "hidden cost", "shipping cost", "storage cost",
    "maintenance cost", "implementation cost", "training cost",
    "switching cost", "integration cost", "overhead",
})

_CLAUSE_OBJECTION_KEYWORDS = frozenset({
    "can't accept", "push back", "not acceptable", "issue with",
    "problem with this clause", "concerns about", "redline",
    "strike this", "remove this section", "modify this term",
    "liability", "indemnification", "limitation of liability",
    "termination clause", "auto-renewal", "payment terms",
    "net 30", "net 60", "net 90", "intellectual property",
})

_MAVERICK_KEYWORDS = frozenset({
    "off-contract", "maverick spend", "non-compliant", "unapproved vendor",
    "bypass", "workaround", "shadow purchasing", "one-off",
})


class ProcurementPack(VerticalPack):
    id = "procurement"
    name = "Procurement & Supplier Intelligence"
    description = (
        "Supplier negotiation intelligence — pricing signals, concession tracking, "
        "commitment language analysis, supplier risk scoring, contract clause objections, "
        "SLA commitments, and TCO analysis. Built to feed S2P platforms."
    )
    industries = [
        "Manufacturing", "Automotive", "Higher Education", "Public Sector",
        "Healthcare", "Life Sciences", "Retail", "CPG", "Energy & Utilities",
        "Financial Services", "Transportation & Logistics",
    ]
    summary_type = "negotiation_brief"

    def extract(self, segment_data: Dict) -> Dict:
        """Enrich extraction with procurement-specific fields."""
        text = " ".join([
            segment_data.get("topic", ""),
            " ".join(segment_data.get("objections", [])),
            " ".join(segment_data.get("decision_signals", [])),
            segment_data.get("transcript", ""),
        ]).lower()

        # --- Pricing signals ---
        pricing = _PRICING_RE.findall(text) or segment_data.get("pricing_signals", [])
        segment_data["pricing_signals"] = pricing[:5]

        # --- Concession detection ---
        concessions = [kw for kw in _CONCESSION_KEYWORDS if kw in text]
        segment_data["concessions_offered"] = concessions

        # --- Commitment strength ---
        strong = sum(1 for kw in _COMMITMENT_STRONG if kw in text)
        weak = sum(1 for kw in _COMMITMENT_WEAK if kw in text)
        if strong > weak:
            segment_data["commitment_strength"] = "strong"
        elif weak > strong:
            segment_data["commitment_strength"] = "weak"
        elif strong > 0:
            segment_data["commitment_strength"] = "mixed"
        else:
            segment_data["commitment_strength"] = "none"

        # --- Supplier risk signals ---
        delivery_risks = [kw for kw in _DELIVERY_RISK_KEYWORDS if kw in text]
        financial_risks = [kw for kw in _FINANCIAL_RISK_KEYWORDS if kw in text]
        compliance_mentions = [kw for kw in _COMPLIANCE_KEYWORDS if kw in text]
        segment_data["delivery_risk_signals"] = delivery_risks
        segment_data["financial_risk_signals"] = financial_risks
        segment_data["compliance_mentions"] = compliance_mentions

        # Composite supplier risk score
        risk_hits = len(delivery_risks) + len(financial_risks)
        segment_data["supplier_risk_score"] = min(risk_hits * 0.2, 1.0)

        # --- SLA commitments ---
        sla_hits = [kw for kw in _SLA_KEYWORDS if kw in text]
        segment_data["sla_commitments_discussed"] = bool(sla_hits)

        # --- Negotiation stage inference ---
        best_stage = "general"
        best_score = 0
        for stage, keywords in _NEGOTIATION_STAGE_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_stage = stage
        segment_data["negotiation_stage"] = best_stage

        # --- Clause objections ---
        clause_issues = [kw for kw in _CLAUSE_OBJECTION_KEYWORDS if kw in text]
        segment_data["clause_objections"] = clause_issues

        # --- Competitor / alternative supplier mentions ---
        alt_suppliers = [kw for kw in _COMPETITOR_SUPPLIER_KEYWORDS if kw in text]
        segment_data["alternative_supplier_signals"] = alt_suppliers

        # --- TCO awareness ---
        tco_hits = [kw for kw in _TCO_KEYWORDS if kw in text]
        segment_data["tco_signals"] = tco_hits

        # --- Maverick spend risk ---
        maverick = any(kw in text for kw in _MAVERICK_KEYWORDS)
        segment_data["maverick_spend_risk"] = maverick

        # --- Negotiation Intelligence (Game Theory layer) ---
        enrich_segment_negotiation_intel(segment_data)

        return segment_data

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="procurement-pack-v1",
            name=self.name,
            description=self.description,
            vertical="procurement",
            fields=[
                FieldDefinition(
                    "topic", FieldType.CATEGORY,
                    "Primary topic of the segment",
                    options=[
                        "pricing", "delivery", "quality", "compliance",
                        "contract_terms", "sla", "relationship", "risk",
                        "sourcing_strategy", "category_review", "general",
                    ],
                ),
                FieldDefinition(
                    "sentiment", FieldType.CATEGORY,
                    "Supplier/buyer sentiment in this segment",
                    options=["positive", "neutral", "negative", "adversarial", "collaborative"],
                ),
                FieldDefinition(
                    "risk", FieldType.CATEGORY,
                    "Supplier risk level",
                    options=["low", "medium", "high"],
                ),
                FieldDefinition(
                    "risk_score", FieldType.NUMBER,
                    "Numeric supplier risk 0.0–1.0",
                ),
                FieldDefinition(
                    "objections", FieldType.LIST_STRING,
                    "Objections raised (contract terms, pricing, delivery, compliance)",
                ),
                FieldDefinition(
                    "decision_signals", FieldType.LIST_STRING,
                    "Signals of forward motion or agreement",
                ),
                FieldDefinition(
                    "pricing_signals", FieldType.LIST_STRING,
                    "Specific prices, per-unit costs, discounts, or rebates mentioned",
                    required=False,
                ),
                FieldDefinition(
                    "concessions_offered", FieldType.LIST_STRING,
                    "Concessions or accommodations offered during negotiation",
                    required=False,
                ),
                FieldDefinition(
                    "commitment_strength", FieldType.CATEGORY,
                    "Strength of verbal commitments (strong/weak/mixed/none)",
                    options=["strong", "weak", "mixed", "none"],
                    required=False,
                ),
                FieldDefinition(
                    "negotiation_stage", FieldType.CATEGORY,
                    "Inferred stage of the negotiation",
                    options=[
                        "rfp_review", "initial_offer", "counter_offer",
                        "final_negotiation", "verbal_agreement",
                    ],
                    required=False,
                ),
                FieldDefinition(
                    "supplier_risk_score", FieldType.NUMBER,
                    "Composite supplier risk score 0.0–1.0",
                    required=False,
                ),
                FieldDefinition(
                    "delivery_risk_signals", FieldType.LIST_STRING,
                    "Delivery/capacity risk indicators",
                    required=False,
                ),
                FieldDefinition(
                    "financial_risk_signals", FieldType.LIST_STRING,
                    "Supplier financial health risk indicators",
                    required=False,
                ),
                FieldDefinition(
                    "compliance_mentions", FieldType.LIST_STRING,
                    "Regulatory, ESG, and certification mentions",
                    required=False,
                ),
                FieldDefinition(
                    "clause_objections", FieldType.LIST_STRING,
                    "Contract clause objections or redlines",
                    required=False,
                ),
                FieldDefinition(
                    "sla_commitments_discussed", FieldType.BOOLEAN,
                    "Were SLA/KPI commitments discussed?",
                    required=False,
                ),
                FieldDefinition(
                    "alternative_supplier_signals", FieldType.LIST_STRING,
                    "Mentions of competing bids or alternative vendors",
                    required=False,
                ),
                FieldDefinition(
                    "tco_signals", FieldType.LIST_STRING,
                    "Total cost of ownership discussion indicators",
                    required=False,
                ),
                FieldDefinition(
                    "maverick_spend_risk", FieldType.BOOLEAN,
                    "Off-contract or non-compliant purchasing risk detected",
                    required=False,
                ),
                # --- Negotiation Intelligence (Game Theory) fields ---
                FieldDefinition(
                    "negotiation_tactics", FieldType.LIST_STRING,
                    "Detected negotiation tactics (anchoring, time_pressure, logrolling, "
                    "walkaway_threat, nibbling, good_cop_bad_cop, highball_lowball, etc.)",
                    required=False,
                ),
                FieldDefinition(
                    "power_balance", FieldType.JSON,
                    "Buyer vs. supplier leverage analysis "
                    "{buyer_leverage, supplier_leverage, dominant_party, leverage_drivers}",
                    required=False,
                ),
                FieldDefinition(
                    "batna_assessment", FieldType.JSON,
                    "Best Alternative to Negotiated Agreement signals for both parties",
                    required=False,
                ),
                FieldDefinition(
                    "escalation_level", FieldType.CATEGORY,
                    "Escalation state of this segment",
                    options=["escalating", "de_escalating", "stable"],
                    required=False,
                ),
                FieldDefinition(
                    "bargaining_style", FieldType.CATEGORY,
                    "Integrative (expanding the pie) vs. distributive (splitting it)",
                    options=["integrative", "distributive", "mixed"],
                    required=False,
                ),
                FieldDefinition(
                    "issues_on_table", FieldType.LIST_STRING,
                    "Active negotiation issues detected (price, delivery, quality, "
                    "contract_terms, compliance, sla, relationship)",
                    required=False,
                ),
                FieldDefinition(
                    "integrative_signals", FieldType.LIST_STRING,
                    "Value-creation and pie-expanding language detected",
                    required=False,
                ),
            ],
        )
