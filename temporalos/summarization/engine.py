"""Auto-summary engine.

Generates structured summaries from a VideoIntelligence result.
MockSummaryEngine is fully rule-based (no LLM required).
LLMSummaryEngine calls OpenAI/Claude with the appropriate template prompt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SummaryType(str, Enum):
    EXECUTIVE = "executive"
    ACTION_ITEMS = "action_items"
    MEETING_NOTES = "meeting_notes"
    DEAL_BRIEF = "deal_brief"
    COACHING_BRIEF = "coaching_brief"
    UX_RESEARCH = "ux_research"
    CS_QBR = "cs_qbr"
    REAL_ESTATE_CONSULT = "real_estate_consult"
    CUSTOM = "custom"


@dataclass
class Summary:
    type: SummaryType
    content: str
    sections: Dict[str, Any]
    word_count: int
    model: str

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "sections": self.sections,
            "word_count": self.word_count,
            "model": self.model,
        }


# ─── Rule-based summarizer (zero external deps) ──────────────────────────────

class MockSummaryEngine:
    """Fully rule-based summary engine from VideoIntelligence data."""

    def generate(
        self,
        intel_dict: Dict[str, Any],
        summary_type: SummaryType,
        custom_template: str = "",
    ) -> Summary:
        segments = intel_dict.get("segments", [])
        all_obj: List[str] = []
        all_sig: List[str] = []
        topics: Dict[str, int] = {}
        high_risk: List[dict] = []

        for seg in segments:
            ext = seg.get("extraction", seg)
            all_obj.extend(ext.get("objections", []))
            all_sig.extend(ext.get("decision_signals", []))
            t = ext.get("topic", "general")
            topics[t] = topics.get(t, 0) + 1
            if ext.get("risk") == "high" or ext.get("risk_score", 0) > 0.6:
                high_risk.append({
                    "timestamp": seg.get("timestamp", seg.get("timestamp_str", "?")),
                    "topic": t,
                })

        dispatch = {
            SummaryType.EXECUTIVE: self._executive,
            SummaryType.ACTION_ITEMS: self._action_items,
            SummaryType.MEETING_NOTES: self._meeting_notes,
            SummaryType.DEAL_BRIEF: self._deal_brief,
            SummaryType.COACHING_BRIEF: self._coaching_brief,
            SummaryType.UX_RESEARCH: self._ux_research,
            SummaryType.CS_QBR: self._cs_qbr,
            SummaryType.REAL_ESTATE_CONSULT: self._real_estate,
            SummaryType.CUSTOM: lambda *_: self._custom(segments, custom_template),
        }

        fn = dispatch.get(summary_type, self._executive)
        return fn(segments, all_obj, all_sig, topics, high_risk)

    # ── Per-type generators ───────────────────────────────────────────────

    def _executive(self, segs, obj, sig, topics, high_risk) -> Summary:
        top = max(topics, key=topics.get) if topics else "general"
        bullets = [
            f"• {len(segs)} segments analyzed across {len(topics)} topic area(s); "
            f"primary focus: {top}.",
            f"• Objections detected: {len(set(obj))} unique — "
            + ("; ".join(list(dict.fromkeys(obj))[:2]) or "none") + ".",
            f"• Decision signals: {len(set(sig))} forward-motion signals — "
            + ("; ".join(list(dict.fromkeys(sig))[:2]) or "none") + ".",
        ]
        if high_risk:
            ts = ", ".join(h["timestamp"] for h in high_risk[:3])
            bullets.append(f"• ⚠ {len(high_risk)} high-risk moments flagged at {ts}.")
        content = "\n".join(bullets)
        return Summary(SummaryType.EXECUTIVE, content,
                       {"bullets": bullets, "top_topic": top},
                       len(content.split()), "rule-based")

    def _action_items(self, segs, obj, sig, topics, high_risk) -> Summary:
        items = [f"{i + 1}. {s}" for i, s in enumerate(dict.fromkeys(sig))]
        content = "\n".join(items) if items else "No action items detected."
        return Summary(SummaryType.ACTION_ITEMS, content,
                       {"items": items, "count": len(items)},
                       len(content.split()), "rule-based")

    def _meeting_notes(self, segs, obj, sig, topics, high_risk) -> Summary:
        topic_list = sorted(topics.items(), key=lambda x: -x[1])
        sections = {
            "topics_covered": [t for t, _ in topic_list],
            "key_objections": list(dict.fromkeys(obj))[:5],
            "action_items": list(dict.fromkeys(sig))[:5],
            "segment_count": len(segs),
            "high_risk_count": len(high_risk),
        }
        lines = (
            ["## Topics Covered"]
            + [f"- {t} ({c} segments)" for t, c in topic_list]
            + ["\n## Key Objections"]
            + ([f"- {o}" for o in sections["key_objections"]] or ["- None raised"])
            + ["\n## Action Items"]
            + ([f"- {a}" for a in sections["action_items"]] or ["- None identified"])
        )
        if high_risk:
            lines += ["\n## Risk Flags",
                      *(f"- [{h['timestamp']}] {h['topic']} segment flagged HIGH" for h in high_risk[:5])]
        content = "\n".join(lines)
        return Summary(SummaryType.MEETING_NOTES, content, sections,
                       len(content.split()), "rule-based")

    def _deal_brief(self, segs, obj, sig, topics, high_risk) -> Summary:
        avg = sum(s.get("extraction", s).get("risk_score", 0) for s in segs) / max(len(segs), 1)
        risk_label = "HIGH" if avg > 0.6 else "MEDIUM" if avg > 0.3 else "LOW"
        sections = {
            "risk_level": risk_label,
            "avg_risk_score": round(avg, 2),
            "top_objections": list(dict.fromkeys(obj))[:3],
            "buying_signals": list(dict.fromkeys(sig))[:3],
            "high_risk_moments": [h["timestamp"] for h in high_risk[:3]],
            "dominant_topic": max(topics, key=topics.get) if topics else "unknown",
        }
        lines = [
            f"**Deal Risk**: {risk_label} (score {sections['avg_risk_score']})",
            f"**Primary Topic**: {sections['dominant_topic']}",
            f"**Top Objections**: {'; '.join(sections['top_objections']) or 'None'}",
            f"**Buying Signals**: {'; '.join(sections['buying_signals']) or 'None'}",
            f"**Risk Moments**: {', '.join(sections['high_risk_moments']) or 'None'}",
        ]
        content = "\n".join(lines)
        return Summary(SummaryType.DEAL_BRIEF, content, sections,
                       len(content.split()), "rule-based")

    def _coaching_brief(self, segs, obj, sig, topics, high_risk) -> Summary:
        avg = sum(s.get("extraction", s).get("risk_score", 0) for s in segs) / max(len(segs), 1)
        sections = {
            "strengths": ["Maintained structured conversation flow",
                          "Identified key customer topics" if topics else "Engaged actively"],
            "improvements": ["Handle pricing objections earlier" if any("pric" in o.lower() for o in obj)
                             else "Deepen discovery questions",
                             "Increase decision signal frequency"],
            "avg_risk_score": round(avg, 2),
            "talk_time_tip": "Aim for 40% talk / 60% listen ratio",
        }
        lines = [
            "## Strengths", *[f"✓ {s}" for s in sections["strengths"]],
            "\n## Areas to Improve", *[f"→ {i}" for i in sections["improvements"]],
            f"\n## Talk Time Guidance\n{sections['talk_time_tip']}",
        ]
        content = "\n".join(lines)
        return Summary(SummaryType.COACHING_BRIEF, content, sections,
                       len(content.split()), "rule-based")

    def _ux_research(self, segs, obj, sig, topics, high_risk) -> Summary:
        sections = {
            "pain_points": list(dict.fromkeys(obj))[:5],
            "feature_requests": list(dict.fromkeys(sig))[:5],
            "confusion_moments": len(high_risk),
            "primary_themes": list(topics.keys())[:4],
        }
        lines = (
            ["## Core Pain Points"]
            + ([f"- {p}" for p in sections["pain_points"]] or ["- None extracted"])
            + ["\n## Feature Requests"]
            + ([f"- {f}" for f in sections["feature_requests"]] or ["- None identified"])
            + [f"\n## Confusion Moments: {sections['confusion_moments']} high-friction segments"]
            + ["\n## Primary Themes"]
            + [f"- {t}" for t in sections["primary_themes"]]
        )
        content = "\n".join(lines)
        return Summary(SummaryType.UX_RESEARCH, content, sections,
                       len(content.split()), "rule-based")

    def _cs_qbr(self, segs, obj, sig, topics, high_risk) -> Summary:
        avg = sum(s.get("extraction", s).get("risk_score", 0) for s in segs) / max(len(segs), 1)
        churn_words = {"cancel", "leave", "renew", "competitor", "cost", "expensive", "not using"}
        churn_signals = [o for o in obj if any(w in o.lower() for w in churn_words)]
        expand_signals = [s for s in sig if any(w in s.lower()
                          for w in {"grow", "team", "seats", "expand", "add"})]
        sections = {
            "health_score": "AT RISK" if avg > 0.5 else "HEALTHY",
            "avg_risk": round(avg, 2),
            "churn_indicators": churn_signals[:3],
            "expansion_signals": expand_signals[:3],
            "action_items": list(dict.fromkeys(sig))[:5],
        }
        lines = (
            [f"**Account Health**: {sections['health_score']} (risk {sections['avg_risk']})"]
            + [f"**Churn Signals**: {'; '.join(churn_signals) or 'None detected'}"]
            + [f"**Expansion Signals**: {'; '.join(expand_signals) or 'None detected'}"]
            + ["\n## CSM Action Items"]
            + ([f"- {a}" for a in sections["action_items"]] or ["- Follow up scheduled"])
        )
        content = "\n".join(lines)
        return Summary(SummaryType.CS_QBR, content, sections,
                       len(content.split()), "rule-based")

    def _real_estate(self, segs, obj, sig, topics, high_risk) -> Summary:
        priority_words = {"bedroom", "bathroom", "kitchen", "office", "garage",
                          "garden", "location", "school", "commute", "size"}
        priorities = [o for o in obj if any(w in o.lower() for w in priority_words)]
        sections = {
            "client_priorities": priorities[:4] or list(dict.fromkeys(obj))[:4],
            "budget_concerns": [o for o in obj if any(w in o.lower()
                                 for w in {"budget", "price", "afford", "expensive", "cost"})][:2],
            "timeline_signals": [s for s in sig if any(w in s.lower()
                                   for w in {"soon", "month", "week", "urgent", "asap"})][:2],
            "recommended_follow_up": list(dict.fromkeys(sig))[:3],
        }
        lines = (
            ["## Client Priorities"]
            + ([f"- {p}" for p in sections["client_priorities"]] or ["- Not specified"])
            + ["\n## Budget Signals"]
            + ([f"- {b}" for b in sections["budget_concerns"]] or ["- No concerns raised"])
            + ["\n## Timeline"]
            + ([f"- {t}" for t in sections["timeline_signals"]] or ["- Flexible"])
            + ["\n## Recommended Follow-up"]
            + ([f"- {r}" for r in sections["recommended_follow_up"]] or ["- Schedule property tour"])
        )
        content = "\n".join(lines)
        return Summary(SummaryType.REAL_ESTATE_CONSULT, content, sections,
                       len(content.split()), "rule-based")

    def _custom(self, segs: list, template: str) -> Summary:
        content = template.replace("{{segment_count}}", str(len(segs)))
        return Summary(SummaryType.CUSTOM, content, {}, len(content.split()), "rule-based")


# ── LLM-powered summarizer (calls real LLM when API key is available) ────────

class LLMSummaryEngine:
    """Generates summaries using the configured LLM provider.

    Falls back to MockSummaryEngine if no LLM provider is available.
    """

    _PROMPTS = {
        SummaryType.EXECUTIVE: (
            "Generate a concise executive summary of this sales call. "
            "Include: key topics discussed, objections raised, decision signals, "
            "and overall risk assessment. Use bullet points."
        ),
        SummaryType.ACTION_ITEMS: (
            "Extract all action items and next steps from this call. "
            "Number each item. Be specific about who should do what."
        ),
        SummaryType.MEETING_NOTES: (
            "Generate structured meeting notes with sections: "
            "Topics Covered, Key Objections, Action Items, Risk Flags."
        ),
        SummaryType.DEAL_BRIEF: (
            "Generate a deal brief: risk level, top objections, buying signals, "
            "dominant topic, and recommended next steps."
        ),
        SummaryType.COACHING_BRIEF: (
            "Generate a coaching brief for the sales rep: strengths observed, "
            "areas to improve, and specific talk-time guidance."
        ),
        SummaryType.UX_RESEARCH: (
            "Generate a UX research synthesis: core pain points, feature requests, "
            "confusion moments, and primary themes."
        ),
        SummaryType.CS_QBR: (
            "Generate a Customer Success QBR report: account health, churn indicators, "
            "expansion signals, and recommended actions."
        ),
        SummaryType.REAL_ESTATE_CONSULT: (
            "Generate a real estate consultation summary: client priorities, "
            "budget signals, timeline, and recommended follow-up."
        ),
    }

    def __init__(self) -> None:
        self._fallback = MockSummaryEngine()

    async def generate(
        self,
        intel_dict: Dict[str, Any],
        summary_type: SummaryType,
        custom_template: str = "",
    ) -> Summary:
        # Try LLM first
        try:
            from temporalos.llm.router import get_llm, MockLLMProvider
            llm = get_llm()
            if isinstance(llm, MockLLMProvider):
                return self._fallback.generate(intel_dict, summary_type, custom_template)
        except Exception:
            return self._fallback.generate(intel_dict, summary_type, custom_template)

        segments = intel_dict.get("segments", [])
        if not segments:
            return self._fallback.generate(intel_dict, summary_type, custom_template)

        # Build context from segments
        context_parts = []
        for i, seg in enumerate(segments[:30]):  # cap at 30 segments for token limits
            ext = seg.get("extraction", seg)
            context_parts.append(
                f"[Segment {i+1} @ {seg.get('timestamp_str', seg.get('timestamp', '?'))}] "
                f"Topic: {ext.get('topic', 'general')} | "
                f"Risk: {ext.get('risk', 'low')} ({ext.get('risk_score', 0):.1%}) | "
                f"Objections: {', '.join(ext.get('objections', [])) or 'none'} | "
                f"Signals: {', '.join(ext.get('decision_signals', [])) or 'none'}"
            )
        context = "\n".join(context_parts)

        system_prompt = (
            "You are an expert business analyst generating structured summaries "
            "from video call intelligence data. Be concise and actionable."
        )
        prompt_template = self._PROMPTS.get(summary_type, "")
        if summary_type == SummaryType.CUSTOM and custom_template:
            prompt_template = custom_template

        prompt = f"{prompt_template}\n\nCall data ({len(segments)} segments):\n{context}"

        try:
            resp = await llm.complete(prompt, system=system_prompt, max_tokens=1024)
            return Summary(
                type=summary_type,
                content=resp.text,
                sections={"raw_response": True, "model": resp.model},
                word_count=len(resp.text.split()),
                model=resp.model,
            )
        except Exception:
            return self._fallback.generate(intel_dict, summary_type, custom_template)


# ── Singleton ────────────────────────────────────────────────────────────────

_engine: Optional[MockSummaryEngine] = None
_llm_engine: Optional[LLMSummaryEngine] = None


def get_summary_engine() -> MockSummaryEngine:
    global _engine
    if _engine is None:
        _engine = MockSummaryEngine()
    return _engine


def get_llm_summary_engine() -> LLMSummaryEngine:
    """Get the LLM-powered summary engine (falls back to rule-based)."""
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMSummaryEngine()
    return _llm_engine


# Type alias for the public interface
SummaryEngine = MockSummaryEngine
