"""Sales & Revenue Intelligence vertical pack."""
from __future__ import annotations
import re
import uuid
from typing import Dict, List
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack

_PRICING_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?(?:\s*[KkMmBb])?|\d+(?:,\d{3})*\s*dollars?", re.I)
_COMPETITOR_KEYWORDS = {"gong", "chorus", "clari", "outreach", "salesloft", "hubspot",
                        "salesforce", "zoho", "pipedrive", "freshsales"}
_URGENCY_KEYWORDS = {"asap", "urgent", "immediately", "right away", "this week",
                     "this month", "deadline", "time-sensitive"}
_CHAMPION_KEYWORDS = {"vp", "director", "head of", "cto", "ceo", "cfo", "decision maker",
                      "budget holder", "final say"}
_DEAL_STAGE_SIGNALS = {
    "discovery": {"tell me about", "what are you looking for", "challenges", "pain point"},
    "demo": {"show you", "walk through", "how it works", "demonstration"},
    "evaluation": {"compare", "evaluate", "trial", "proof of concept", "poc"},
    "negotiation": {"pricing", "discount", "contract", "terms", "proposal"},
    "closed-won": {"let's go", "sign", "ready to move", "start onboarding"},
}


class SalesPack(VerticalPack):
    id = "sales"
    name = "Sales"
    description = (
        "Deep sales call analysis — objections, pricing signals, deal risk scoring, "
        "rep benchmarks, talk ratio, and next-step discovery."
    )
    industries = ["SaaS", "Enterprise Sales", "Insurance", "Real Estate Sales",
                  "Financial Services", "Recruiting"]
    summary_type = "deal_brief"

    def extract(self, segment_data: Dict) -> Dict:
        """Enrich extraction with sales-specific fields."""
        text = " ".join([
            segment_data.get("topic", ""),
            " ".join(segment_data.get("objections", [])),
            " ".join(segment_data.get("decision_signals", [])),
            segment_data.get("transcript", ""),
        ]).lower()

        # Pricing mentions
        pricing = _PRICING_RE.findall(text) or segment_data.get("pricing_mentions", [])
        segment_data["pricing_mentions"] = pricing[:5]

        # Competitor mentions
        competitors = [c for c in _COMPETITOR_KEYWORDS if c in text]
        segment_data["competitor_mentions"] = competitors or segment_data.get("competitor_mentions", [])

        # Champion detection
        champion = any(kw in text for kw in _CHAMPION_KEYWORDS)
        segment_data["champion_present"] = champion

        # Deal stage inference
        best_stage = "general"
        best_score = 0
        for stage, keywords in _DEAL_STAGE_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_stage = stage
        if best_score > 0:
            segment_data["deal_stage"] = best_stage

        # Urgency level
        urgency_count = sum(1 for kw in _URGENCY_KEYWORDS if kw in text)
        segment_data["urgency_level"] = (
            "high" if urgency_count >= 2 else "medium" if urgency_count == 1 else "low"
        )

        return segment_data

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="sales-pack-v1",
            name=self.name,
            description=self.description,
            vertical="sales",
            fields=[
                FieldDefinition("topic", FieldType.CATEGORY, "Primary topic of the segment",
                                options=["pricing", "competition", "features", "timeline",
                                         "security", "onboarding", "support", "general"]),
                FieldDefinition("sentiment", FieldType.CATEGORY, "Customer sentiment",
                                options=["positive", "neutral", "negative", "hesitant"]),
                FieldDefinition("risk", FieldType.CATEGORY, "Deal risk level",
                                options=["low", "medium", "high"]),
                FieldDefinition("risk_score", FieldType.NUMBER,
                                "Numeric risk 0.0–1.0"),
                FieldDefinition("objections", FieldType.LIST_STRING,
                                "Sales objections raised"),
                FieldDefinition("decision_signals", FieldType.LIST_STRING,
                                "Forward-motion buying signals"),
                FieldDefinition("pricing_mentions", FieldType.LIST_STRING,
                                "Specific prices, discounts, or budget figures mentioned",
                                required=False),
                FieldDefinition("competitor_mentions", FieldType.LIST_STRING,
                                "Competitors or alternatives named", required=False),
                FieldDefinition("champion_present", FieldType.BOOLEAN,
                                "Is an internal champion / decision-maker present?",
                                required=False),
                FieldDefinition("deal_stage", FieldType.CATEGORY,
                                "Inferred deal stage",
                                options=["discovery", "demo", "evaluation",
                                         "negotiation", "closed-won", "closed-lost"],
                                required=False),
                FieldDefinition("rep_talk_percentage", FieldType.NUMBER,
                                "Rep's share of speaking time (0–100)", required=False),
                FieldDefinition("urgency_level", FieldType.CATEGORY,
                                "Customer urgency signal",
                                options=["low", "medium", "high"], required=False),
            ],
        )
