"""Real Estate client consultation vertical pack."""
from __future__ import annotations
import re
from typing import Dict, List
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack

_BUDGET_RE = re.compile(r"\$[\d,]+(?:k|m)?|\d+\s*(?:thousand|million|k)\b", re.IGNORECASE)
_TIMELINE_SIGNALS = {
    "immediately": {"asap", "right away", "immediately", "urgent", "this week"},
    "1_month": {"next month", "30 days", "within a month", "couple weeks"},
    "3_months": {"few months", "90 days", "quarter", "this quarter"},
    "6_months": {"six months", "half year", "end of year"},
    "just_browsing": {"just looking", "no rush", "browsing", "exploring"},
}
_OBJECTION_KEYWORDS = {"too small", "too big", "old", "noisy", "far from",
                       "no parking", "no yard", "expensive", "needs work",
                       "renovation", "outdated", "condition"}
_PRIORITY_KEYWORDS = {"school", "bedroom", "bathroom", "garage", "kitchen",
                      "backyard", "pool", "quiet", "walkable", "public transit",
                      "downtown", "suburban", "modern", "open floor"}
_FINANCING_SIGNALS = {
    "pre_approved": {"pre-approved", "preapproved", "pre approved"},
    "cash_buyer": {"cash offer", "cash buyer", "all cash", "no mortgage"},
    "needs_mortgage": {"mortgage", "loan", "financing", "lender"},
}


class RealEstatePack(VerticalPack):
    id = "real_estate"
    name = "Real Estate Client Consultations"
    description = (
        "Extract client priorities, budget signals, property objections, timeline urgency, "
        "and decision criteria from real estate consultations and walkthroughs."
    )
    industries = ["Residential Real Estate", "Commercial Real Estate",
                  "Property Management", "Mortgage Brokerage"]
    summary_type = "real_estate_consult"

    def _vertical_extract(self, segment_data: Dict) -> Dict:
        text = " ".join([
            segment_data.get("topic", ""),
            " ".join(segment_data.get("objections", [])),
            " ".join(segment_data.get("decision_signals", [])),
            segment_data.get("transcript", ""),
        ]).lower()

        # Budget signals
        budget_matches = _BUDGET_RE.findall(text)
        if budget_matches:
            segment_data["budget_signals"] = budget_matches

        # Timeline urgency
        for level, keywords in _TIMELINE_SIGNALS.items():
            if any(kw in text for kw in keywords):
                segment_data["timeline_urgency"] = level
                break
        else:
            segment_data["timeline_urgency"] = "flexible"

        # Property objections
        objections = [kw for kw in _OBJECTION_KEYWORDS if kw in text]
        if objections:
            segment_data["property_objections"] = objections

        # Client priorities
        priorities = [kw for kw in _PRIORITY_KEYWORDS if kw in text]
        if priorities:
            segment_data["client_priorities"] = priorities

        # Financing status
        for status, keywords in _FINANCING_SIGNALS.items():
            if any(kw in text for kw in keywords):
                segment_data["financing_status"] = status
                break

        return segment_data

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="real-estate-pack-v1",
            name=self.name,
            description=self.description,
            vertical="real_estate",
            fields=[
                FieldDefinition("topic", FieldType.CATEGORY,
                                "Primary consultation topic",
                                options=["property_features", "pricing_negotiation",
                                         "location", "timeline", "financing",
                                         "comparison", "objections", "general"]),
                FieldDefinition("client_priorities", FieldType.LIST_STRING,
                                "Property features or requirements the client emphasized"),
                FieldDefinition("budget_signals", FieldType.LIST_STRING,
                                "Budget range, financing concerns, or price sensitivity signals",
                                required=False),
                FieldDefinition("property_objections", FieldType.LIST_STRING,
                                "Specific property concerns or dislikes raised"),
                FieldDefinition("timeline_urgency", FieldType.CATEGORY,
                                "How urgently the client needs to move",
                                options=["immediately", "1_month", "3_months",
                                         "6_months", "flexible", "just_browsing"]),
                FieldDefinition("decision_criteria", FieldType.LIST_STRING,
                                "Must-have criteria the client stated",
                                required=False),
                FieldDefinition("sentiment", FieldType.CATEGORY,
                                "Overall client sentiment for this property/segment",
                                options=["very_positive", "positive", "neutral",
                                         "negative", "very_negative"]),
                FieldDefinition("comparison_properties", FieldType.LIST_STRING,
                                "Other properties mentioned for comparison",
                                required=False),
                FieldDefinition("financing_status", FieldType.CATEGORY,
                                "Client's financing situation",
                                options=["pre_approved", "in_progress", "cash_buyer",
                                         "needs_mortgage", "unknown"],
                                required=False),
                FieldDefinition("decision_signals", FieldType.LIST_STRING,
                                "Signs of interest or readiness to proceed",
                                required=False),
                FieldDefinition("risk_score", FieldType.NUMBER,
                                "Likelihood of losing this client (0.0–1.0)"),
                FieldDefinition("recommended_follow_up", FieldType.LIST_STRING,
                                "Specific follow-up actions for the agent"),
            ],
        )
