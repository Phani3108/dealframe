"""UX Research vertical pack."""
from __future__ import annotations
from typing import Dict, List
from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
from temporalos.verticals.base import VerticalPack

_PAIN_KEYWORDS = {"frustrating", "annoying", "difficult", "hard to", "can't find",
                  "confusing", "broken", "doesn't work", "bug", "slow"}
_DELIGHT_KEYWORDS = {"love", "great", "amazing", "easy", "intuitive", "perfect",
                     "awesome", "exactly what", "impressed"}
_CONFUSION_KEYWORDS = {"confused", "don't understand", "what does", "where is",
                       "how do i", "lost", "unclear", "not sure"}
_FEATURE_KEYWORDS = {"wish", "it would be nice", "should have", "need", "want",
                     "missing", "add", "feature request"}


class UXResearchPack(VerticalPack):
    id = "ux_research"
    name = "UX Research & User Interviews"
    description = (
        "Structured coding of user interviews and usability sessions — pain points, "
        "feature requests, confusion moments, delight signals, and task success."
    )
    industries = ["Product Management", "UX Design", "SaaS", "Consumer Apps",
                  "Healthcare UX", "Fintech", "EdTech"]
    summary_type = "ux_research"

    def extract(self, segment_data: Dict) -> Dict:
        text = " ".join([
            segment_data.get("topic", ""),
            " ".join(segment_data.get("objections", [])),
            segment_data.get("transcript", ""),
        ]).lower()

        pain = [kw for kw in _PAIN_KEYWORDS if kw in text]
        delight = [kw for kw in _DELIGHT_KEYWORDS if kw in text]
        confusion = [kw for kw in _CONFUSION_KEYWORDS if kw in text]
        features = [kw for kw in _FEATURE_KEYWORDS if kw in text]

        segment_data["pain_points"] = segment_data.get("pain_points", []) + pain
        segment_data["delight_moments"] = delight
        segment_data["confusion_signals"] = confusion
        segment_data["feature_requests"] = segment_data.get("feature_requests", []) + features

        if pain or confusion:
            segment_data["segment_type"] = "pain_point" if pain else "confusion"
            segment_data["severity"] = "major" if len(pain) >= 2 else "minor"
        elif delight:
            segment_data["segment_type"] = "delight"
        elif features:
            segment_data["segment_type"] = "feature_request"

        return segment_data

    def schema(self) -> SchemaDefinition:
        return SchemaDefinition(
            id="ux-research-pack-v1",
            name=self.name,
            description=self.description,
            vertical="ux_research",
            fields=[
                FieldDefinition("segment_type", FieldType.CATEGORY,
                                "Type of observed moment",
                                options=["pain_point", "feature_request", "delight",
                                         "confusion", "task_attempt", "question",
                                         "comparison", "general"]),
                FieldDefinition("topic", FieldType.CATEGORY,
                                "Product area being discussed",
                                options=["onboarding", "core_workflow", "navigation",
                                         "search", "collaboration", "pricing",
                                         "integrations", "support", "general"]),
                FieldDefinition("pain_points", FieldType.LIST_STRING,
                                "User pain points expressed verbatim or paraphrased"),
                FieldDefinition("feature_requests", FieldType.LIST_STRING,
                                "Explicit or implicit feature requests"),
                FieldDefinition("confusion_signals", FieldType.LIST_STRING,
                                "Signs of confusion: hesitation, backtracking, questions",
                                required=False),
                FieldDefinition("delight_moments", FieldType.LIST_STRING,
                                "Positive reactions and moments of satisfaction",
                                required=False),
                FieldDefinition("task_success", FieldType.CATEGORY,
                                "Task completion outcome",
                                options=["success", "partial", "failure", "not_applicable"],
                                required=False),
                FieldDefinition("severity", FieldType.CATEGORY,
                                "Severity of the pain point (if any)",
                                options=["critical", "major", "minor", "none"],
                                required=False),
                FieldDefinition("sentiment", FieldType.CATEGORY,
                                "User emotional tone",
                                options=["positive", "neutral", "frustrated",
                                         "confused", "delighted"]),
                FieldDefinition("persona_signals", FieldType.LIST_STRING,
                                "Clues about user's role, experience level, or context",
                                required=False),
                FieldDefinition("verbatim_quote", FieldType.STRING,
                                "Most insightful direct quote from this segment",
                                required=False),
                FieldDefinition("competitive_mentions", FieldType.LIST_STRING,
                                "Competing tools or workflows mentioned", required=False),
            ],
        )
