"""Negotiation Intelligence Analyzer — Game Theory & Behavioral Economics.

Applies negotiation science frameworks to procurement conversation segments:
- Nash equilibrium approximation from revealed price preferences
- ZOPA (Zone of Possible Agreement) estimation
- BATNA signal detection
- Concession pattern classification (tit-for-tat, gradual, front-loaded)
- Tactical pattern recognition (anchoring, time pressure, logrolling, etc.)
- Power balance tracking across the conversation
- Integrative vs. distributive bargaining classification
- Multi-issue linkage and value-creation opportunity detection

This module sits in the intelligence layer and is called:
  1. Per-segment: from ProcurementPack.extract() for tactical enrichment
  2. Per-session: from pipeline post-processing for strategic analysis
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants — Negotiation Tactics & Behavioral Signals
# ---------------------------------------------------------------------------

# Tactics taxonomy: each tactic maps to keyword/phrase patterns
_TACTICS: Dict[str, Tuple[frozenset, str]] = {
    "anchoring": (
        frozenset({
            "our standard price", "list price", "retail price",
            "market rate is", "typically goes for", "normally priced at",
            "starting point", "our proposal is", "came in at",
        }),
        "Setting a reference point to influence the negotiation range",
    ),
    "time_pressure": (
        frozenset({
            "end of quarter", "deadline", "runs out", "expires",
            "limited time", "need to decide", "by friday", "by end of week",
            "window is closing", "can't hold this", "offer expires",
            "before the board meeting", "fiscal year end",
        }),
        "Using urgency or deadlines to force faster concessions",
    ),
    "nibbling": (
        frozenset({
            "one more thing", "by the way", "while we're at it",
            "could you also", "throw in", "include at no",
            "small addition", "just one more", "on top of that",
        }),
        "Requesting small add-ons after the main deal seems settled",
    ),
    "good_cop_bad_cop": (
        frozenset({
            "my manager won't approve", "legal won't accept",
            "our cfo insists", "procurement policy requires",
            "i want to help but", "my hands are tied",
            "i need to check with", "let me escalate",
        }),
        "Invoking higher authority to apply pressure while appearing sympathetic",
    ),
    "logrolling": (
        frozenset({
            "if you can do", "in exchange for", "trade-off",
            "we'd be willing to", "in return", "quid pro quo",
            "if you handle", "we can agree on",
            "bundle", "package deal",
        }),
        "Trading concessions across multiple issues to create mutual value",
    ),
    "highball_lowball": (
        frozenset({
            "above market", "way too high", "significantly above",
            "well below", "unreasonable", "not in the ballpark",
            "far from what we expected", "wildly off",
        }),
        "Making an extreme opening offer to shift the negotiation range",
    ),
    "fait_accompli": (
        frozenset({
            "already decided", "board approved", "contract is ready",
            "we've committed", "already sourced", "signed off",
            "it's done", "no going back",
        }),
        "Presenting a decision as already made to limit counterparty options",
    ),
    "silence_flinch": (
        frozenset({
            "pause", "hesitat", "long silence", "let me think",
            "i'm not sure about that", "that gives me pause",
        }),
        "Using silence or visible reaction to create doubt about an offer",
    ),
    "reciprocal_concession": (
        frozenset({
            "meet halfway", "split the difference", "we'll move if you move",
            "give and take", "mutual concession", "match our move",
            "we came down, now", "meet you in the middle",
        }),
        "Requesting a proportional concession in return for one given",
    ),
    "walkaway_threat": (
        frozenset({
            "walk away", "deal breaker", "non-starter", "showstopper",
            "no deal", "we'll go elsewhere", "take our business",
            "other options", "plan b",
        }),
        "Threatening to exit the negotiation to maximize concessions",
    ),
}

# BATNA signal keywords — separated by party
_BATNA_BUYER = frozenset({
    "other supplier", "alternative vendor", "competing bid", "other quote",
    "incumbent", "current provider", "switch", "replacement",
    "we have options", "several bidders", "rfp responses",
})

_BATNA_SUPPLIER = frozenset({
    "other customer", "high demand", "limited capacity", "wait list",
    "allocation", "oversubscribed", "exclusive", "sole source",
    "no one else offers", "proprietary", "patented",
})

# Integrative (value-creating) vs. distributive (zero-sum) signals
_INTEGRATIVE_SIGNALS = frozenset({
    "what else can", "expand the scope", "additional value",
    "bundle", "package", "creative solution", "mutual benefit",
    "win-win", "long-term partnership", "joint investment",
    "value-add", "strategic relationship", "co-develop",
    "volume commitment", "multi-year", "preferred supplier",
})

_DISTRIBUTIVE_SIGNALS = frozenset({
    "split the difference", "take it or leave", "final offer",
    "non-negotiable", "fixed price", "bottom line", "our limit",
    "cost is cost", "zero-sum", "either or", "one or the other",
})

# Escalation / de-escalation
_ESCALATION_SIGNALS = frozenset({
    "escalate", "involve management", "legal review", "formal complaint",
    "breach", "penalty", "consequences", "unacceptable", "walk away",
    "deal breaker", "non-starter", "not acceptable",
})

_DEESCALATION_SIGNALS = frozenset({
    "let's find a way", "work together", "compromise", "flexible",
    "open to", "accommodate", "understand your position", "partnership",
    "collaborate", "good faith", "appreciate", "reasonable",
})

# Multi-issue keywords with issue categories
_ISSUE_CATEGORIES = {
    "price": {"price", "cost", "per unit", "discount", "rate", "pricing",
              "rebate", "volume tier", "$"},
    "delivery": {"lead time", "delivery", "shipping", "logistics", "on-time",
                 "warehouse", "freight", "ddp", "dap"},
    "quality": {"quality", "defect", "inspection", "specification", "tolerance",
                "certification", "iso", "testing"},
    "contract_terms": {"auto-renewal", "liability", "indemnification", "termination",
                       "payment terms", "net 30", "net 60", "ip", "intellectual property"},
    "compliance": {"esg", "sustainability", "carbon", "audit", "regulatory",
                   "environmental", "labor", "diversity", "gdpr", "soc"},
    "sla": {"sla", "service level", "uptime", "kpi", "penalty clause", "credit",
            "response time", "99."},
    "relationship": {"partnership", "long-term", "preferred", "strategic",
                     "multi-year", "exclusivity"},
}

# Price extraction pattern (reuse-compatible with procurement.py)
_PRICE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{1,2})?)", re.I
)


# ---------------------------------------------------------------------------
# Data classes — Structured output
# ---------------------------------------------------------------------------

@dataclass
class TacticDetection:
    """A detected negotiation tactic in a segment."""
    tactic: str
    confidence: float  # 0.0–1.0 based on keyword hit density
    description: str
    keywords_matched: List[str]


@dataclass
class PowerBalance:
    """Relative leverage between buyer and supplier."""
    buyer_leverage: float   # 0.0–1.0
    supplier_leverage: float  # 0.0–1.0
    dominant_party: str     # "buyer", "supplier", "balanced"
    leverage_drivers: List[str]  # what's driving the balance


@dataclass
class BATNAAssessment:
    """Best Alternative to Negotiated Agreement signals."""
    buyer_batna_signals: List[str]
    supplier_batna_signals: List[str]
    buyer_batna_strength: str   # "strong", "moderate", "weak", "none"
    supplier_batna_strength: str


@dataclass
class SegmentNegotiationIntel:
    """Per-segment negotiation intelligence."""
    tactics_detected: List[TacticDetection]
    power_balance: PowerBalance
    batna: BATNAAssessment
    escalation_level: str     # "escalating", "de_escalating", "stable"
    bargaining_style: str     # "integrative", "distributive", "mixed"
    issues_on_table: List[str]  # active negotiation issues in this segment
    integrative_signals: List[str]
    distributive_signals: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AnchorAnalysis:
    """First-mover anchoring effect analysis."""
    anchor_party: str       # who set the first price
    anchor_price: float
    counter_prices: List[float]
    final_price: Optional[float]
    anchor_effect: float    # 0–1: how close final is to anchor (1 = anchor held)
    drift_from_anchor: float  # absolute distance


@dataclass
class ConcessionEvent:
    """A single concession tracked across the negotiation."""
    segment_index: int
    party: str
    description: str
    magnitude: Optional[float]  # dollar value if pricing-related


@dataclass
class ZOPAEstimate:
    """Zone of Possible Agreement from revealed preferences."""
    buyer_ceiling: Optional[float]   # highest price buyer might accept
    supplier_floor: Optional[float]  # lowest price supplier might accept
    overlap: bool
    zopa_range: Optional[Tuple[float, float]]
    confidence: str  # "high", "medium", "low" based on data availability


@dataclass
class NashEquilibriumEstimate:
    """Simplified Nash equilibrium approximation."""
    estimated_agreement_point: Optional[float]
    method: str  # "zopa_midpoint", "leverage_adjusted", "insufficient_data"
    buyer_utility: float   # 0–1 estimate
    supplier_utility: float
    pareto_optimal: bool   # is the estimate on the Pareto frontier?
    rationale: str


@dataclass
class SessionNegotiationReport:
    """Full negotiation intelligence report across all segments."""
    zopa: ZOPAEstimate
    nash_equilibrium: NashEquilibriumEstimate
    anchor_analysis: Optional[AnchorAnalysis]
    concession_trajectory: List[ConcessionEvent]
    concession_pattern: str  # "tit_for_tat", "gradual", "front_loaded", "one_sided", "none"
    power_shift_timeline: List[Dict]  # [{segment, buyer_leverage, supplier_leverage}]
    deal_health: str         # "converging", "stalled", "diverging"
    issues_resolved: List[str]
    issues_open: List[str]
    value_creation_opportunities: List[str]
    recommended_moves: List[str]
    overall_tactics_summary: Dict[str, int]  # tactic → count across session

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core Analyzer
# ---------------------------------------------------------------------------

class NegotiationAnalyzer:
    """Analyzes negotiation dynamics using game theory and behavioral economics.

    Per-segment: detects tactics, power balance, BATNA, escalation, and
    bargaining style.

    Per-session: synthesizes ZOPA, Nash equilibrium, concession patterns,
    anchor effects, power shifts, and strategic recommendations.
    """

    # -- Per-Segment Analysis --------------------------------------------------

    def analyze_segment(self, segment_data: Dict, segment_index: int = 0) -> SegmentNegotiationIntel:
        """Analyze a single negotiation segment for tactical intelligence."""
        text = _extract_text(segment_data)

        tactics = self._detect_tactics(text)
        batna = self._assess_batna(text)
        power = self._assess_power_balance(text, batna, segment_data)
        escalation = self._assess_escalation(text)
        bargaining = self._assess_bargaining_style(text)
        issues = self._detect_issues(text)
        integrative = [s for s in _INTEGRATIVE_SIGNALS if s in text]
        distributive = [s for s in _DISTRIBUTIVE_SIGNALS if s in text]

        return SegmentNegotiationIntel(
            tactics_detected=tactics,
            power_balance=power,
            batna=batna,
            escalation_level=escalation,
            bargaining_style=bargaining,
            issues_on_table=issues,
            integrative_signals=integrative,
            distributive_signals=distributive,
        )

    def _detect_tactics(self, text: str) -> List[TacticDetection]:
        """Scan text for negotiation tactics from the taxonomy."""
        detected = []
        for tactic_name, (keywords, description) in _TACTICS.items():
            matched = [kw for kw in keywords if kw in text]
            if matched:
                confidence = min(len(matched) / 3.0, 1.0)
                detected.append(TacticDetection(
                    tactic=tactic_name,
                    confidence=round(confidence, 2),
                    description=description,
                    keywords_matched=matched,
                ))
        return detected

    def _assess_batna(self, text: str) -> BATNAAssessment:
        buyer_signals = [kw for kw in _BATNA_BUYER if kw in text]
        supplier_signals = [kw for kw in _BATNA_SUPPLIER if kw in text]

        def _strength(signals: List[str]) -> str:
            n = len(signals)
            if n >= 3:
                return "strong"
            if n >= 2:
                return "moderate"
            if n >= 1:
                return "weak"
            return "none"

        return BATNAAssessment(
            buyer_batna_signals=buyer_signals,
            supplier_batna_signals=supplier_signals,
            buyer_batna_strength=_strength(buyer_signals),
            supplier_batna_strength=_strength(supplier_signals),
        )

    def _assess_power_balance(
        self, text: str, batna: BATNAAssessment, segment_data: Dict
    ) -> PowerBalance:
        """Estimate leverage from BATNA strength, alternatives, urgency, and
        commitment asymmetry."""
        buyer_score = 0.0
        supplier_score = 0.0
        drivers: List[str] = []

        # BATNA contribution
        batna_map = {"strong": 0.35, "moderate": 0.2, "weak": 0.1, "none": 0.0}
        buyer_score += batna_map.get(batna.buyer_batna_strength, 0)
        supplier_score += batna_map.get(batna.supplier_batna_strength, 0)
        if batna.buyer_batna_strength != "none":
            drivers.append(f"buyer_batna_{batna.buyer_batna_strength}")
        if batna.supplier_batna_strength != "none":
            drivers.append(f"supplier_batna_{batna.supplier_batna_strength}")

        # Alternative mention boost
        if any(kw in text for kw in ("other supplier", "competing bid", "other quote")):
            buyer_score += 0.15
            drivers.append("buyer_has_alternatives")
        if any(kw in text for kw in ("high demand", "sole source", "proprietary")):
            supplier_score += 0.15
            drivers.append("supplier_scarcity")

        # Urgency asymmetry
        if any(kw in text for kw in ("need to decide", "deadline", "end of quarter")):
            # Time pressure usually benefits the party NOT under pressure
            # Heuristic: if buyer mentions urgency, supplier gains leverage
            supplier_score += 0.1
            drivers.append("buyer_urgency_benefits_supplier")

        # Commitment asymmetry
        commitment = segment_data.get("commitment_strength", "none")
        if commitment == "strong":
            supplier_score += 0.1
            drivers.append("supplier_strong_commitment")
        elif commitment == "weak":
            buyer_score += 0.1
            drivers.append("supplier_weak_commitment_benefits_buyer")

        # Concession count
        concessions = segment_data.get("concessions_offered", [])
        if len(concessions) >= 2:
            buyer_score += 0.1
            drivers.append("supplier_making_concessions")

        # Normalize to 0–1
        total = buyer_score + supplier_score
        if total > 0:
            buyer_lev = round(buyer_score / total, 2)
            supplier_lev = round(supplier_score / total, 2)
        else:
            buyer_lev = supplier_lev = 0.5

        if abs(buyer_lev - supplier_lev) < 0.1:
            dominant = "balanced"
        elif buyer_lev > supplier_lev:
            dominant = "buyer"
        else:
            dominant = "supplier"

        return PowerBalance(
            buyer_leverage=buyer_lev,
            supplier_leverage=supplier_lev,
            dominant_party=dominant,
            leverage_drivers=drivers,
        )

    def _assess_escalation(self, text: str) -> str:
        esc = sum(1 for kw in _ESCALATION_SIGNALS if kw in text)
        deesc = sum(1 for kw in _DEESCALATION_SIGNALS if kw in text)
        if esc > deesc and esc > 0:
            return "escalating"
        if deesc > esc and deesc > 0:
            return "de_escalating"
        return "stable"

    def _assess_bargaining_style(self, text: str) -> str:
        integrative = sum(1 for s in _INTEGRATIVE_SIGNALS if s in text)
        distributive = sum(1 for s in _DISTRIBUTIVE_SIGNALS if s in text)
        if integrative > distributive:
            return "integrative"
        if distributive > integrative:
            return "distributive"
        if integrative > 0:
            return "mixed"
        return "mixed"

    def _detect_issues(self, text: str) -> List[str]:
        """Identify active negotiation issues in this segment."""
        active = []
        for issue, keywords in _ISSUE_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                active.append(issue)
        return active

    # -- Session-Level (Multi-Segment) Analysis --------------------------------

    def analyze_session(self, segments: List[Dict]) -> SessionNegotiationReport:
        """Strategic analysis across an entire negotiation session.

        Takes a list of segment_data dicts (already enriched by
        ProcurementPack.extract and analyze_segment) and produces a
        session-level negotiation intelligence report.
        """
        # Collect per-segment intel
        segment_intels: List[SegmentNegotiationIntel] = []
        for i, seg in enumerate(segments):
            intel = self.analyze_segment(seg, segment_index=i)
            segment_intels.append(intel)

        # Extract price points from all segments
        all_prices = self._collect_prices(segments)
        buyer_prices, supplier_prices = self._classify_prices(segments, all_prices)

        # ZOPA
        zopa = self._estimate_zopa(buyer_prices, supplier_prices)

        # Anchor analysis
        anchor = self._analyze_anchoring(segments, all_prices)

        # Concession trajectory
        concessions = self._build_concession_trajectory(segments)
        concession_pattern = self._classify_concession_pattern(concessions)

        # Nash equilibrium
        nash = self._estimate_nash(zopa, segment_intels, all_prices)

        # Power shift timeline
        power_timeline = [
            {
                "segment": i,
                "buyer_leverage": intel.power_balance.buyer_leverage,
                "supplier_leverage": intel.power_balance.supplier_leverage,
            }
            for i, intel in enumerate(segment_intels)
        ]

        # Deal health
        deal_health = self._assess_deal_health(segment_intels, concessions)

        # Issue tracking
        all_issues: set = set()
        for intel in segment_intels:
            all_issues.update(intel.issues_on_table)
        resolved = self._detect_resolved_issues(segments)
        open_issues = [i for i in all_issues if i not in resolved]

        # Value creation opportunities
        value_ops = self._identify_value_creation(segments, segment_intels)

        # Recommendations
        recommendations = self._generate_recommendations(
            zopa, nash, segment_intels, concessions, open_issues, deal_health
        )

        # Tactics summary
        tactics_summary: Dict[str, int] = {}
        for intel in segment_intels:
            for t in intel.tactics_detected:
                tactics_summary[t.tactic] = tactics_summary.get(t.tactic, 0) + 1

        return SessionNegotiationReport(
            zopa=zopa,
            nash_equilibrium=nash,
            anchor_analysis=anchor,
            concession_trajectory=concessions,
            concession_pattern=concession_pattern,
            power_shift_timeline=power_timeline,
            deal_health=deal_health,
            issues_resolved=list(resolved),
            issues_open=open_issues,
            value_creation_opportunities=value_ops,
            recommended_moves=recommendations,
            overall_tactics_summary=tactics_summary,
        )

    # -- Price Analysis Helpers ------------------------------------------------

    def _collect_prices(self, segments: List[Dict]) -> List[float]:
        """Extract all dollar amounts mentioned across segments."""
        prices = []
        for seg in segments:
            text = _extract_text(seg)
            for m in _PRICE_RE.finditer(text):
                try:
                    val = float(m.group(1).replace(",", ""))
                    prices.append(val)
                except ValueError:
                    continue
        return prices

    def _classify_prices(
        self, segments: List[Dict], all_prices: List[float]
    ) -> Tuple[List[float], List[float]]:
        """Separate prices into buyer-mentioned vs. supplier-mentioned.

        Uses speaker labels or segment speaker info if available.
        Falls back to position heuristic (odd/even).
        """
        buyer_prices: List[float] = []
        supplier_prices: List[float] = []

        for i, seg in enumerate(segments):
            text = _extract_text(seg)
            seg_prices = [
                float(m.group(1).replace(",", ""))
                for m in _PRICE_RE.finditer(text)
            ]
            speaker = seg.get("speaker", "").lower()
            is_supplier = "supplier" in speaker or "account" in speaker or "vendor" in speaker
            is_buyer = "buyer" in speaker or "category" in speaker or "procurement" in speaker
            # Explicit label takes priority, fall back to even/odd heuristic
            if is_supplier:
                for p in seg_prices:
                    supplier_prices.append(p)
            elif is_buyer:
                for p in seg_prices:
                    buyer_prices.append(p)
            else:
                # No label — use position heuristic (even=buyer, odd=supplier)
                for p in seg_prices:
                    if i % 2 == 0:
                        buyer_prices.append(p)
                    else:
                        supplier_prices.append(p)

        return buyer_prices, supplier_prices

    def _estimate_zopa(
        self, buyer_prices: List[float], supplier_prices: List[float]
    ) -> ZOPAEstimate:
        """Estimate ZOPA from revealed price points.

        Buyer ceiling = highest price buyer mentions (reservation price proxy).
        Supplier floor = lowest price supplier mentions.
        """
        if not buyer_prices and not supplier_prices:
            return ZOPAEstimate(
                buyer_ceiling=None, supplier_floor=None,
                overlap=False, zopa_range=None, confidence="low",
            )

        buyer_ceil = max(buyer_prices) if buyer_prices else None
        supplier_floor = min(supplier_prices) if supplier_prices else None

        if buyer_ceil is not None and supplier_floor is not None:
            overlap = buyer_ceil >= supplier_floor
            zopa_range = (supplier_floor, buyer_ceil) if overlap else None
            confidence = "high" if len(buyer_prices) >= 2 and len(supplier_prices) >= 2 else "medium"
        else:
            overlap = False
            zopa_range = None
            confidence = "low"

        return ZOPAEstimate(
            buyer_ceiling=buyer_ceil,
            supplier_floor=supplier_floor,
            overlap=overlap,
            zopa_range=zopa_range,
            confidence=confidence,
        )

    def _analyze_anchoring(
        self, segments: List[Dict], all_prices: List[float]
    ) -> Optional[AnchorAnalysis]:
        """Detect who anchored first and measure anchor drift."""
        if not all_prices:
            return None

        # Find first price mention and its speaker
        anchor_price = all_prices[0]
        anchor_party = "unknown"
        for seg in segments:
            text = _extract_text(seg)
            if _PRICE_RE.search(text):
                speaker = seg.get("speaker", "").lower()
                if "buyer" in speaker or "category" in speaker:
                    anchor_party = "buyer"
                elif "supplier" in speaker or "account" in speaker:
                    anchor_party = "supplier"
                break

        final_price = all_prices[-1] if len(all_prices) > 1 else None
        counter_prices = all_prices[1:] if len(all_prices) > 1 else []

        if final_price is not None and anchor_price > 0:
            drift = abs(final_price - anchor_price)
            anchor_effect = max(0.0, 1.0 - drift / anchor_price)
        else:
            drift = 0.0
            anchor_effect = 1.0

        return AnchorAnalysis(
            anchor_party=anchor_party,
            anchor_price=anchor_price,
            counter_prices=counter_prices,
            final_price=final_price,
            anchor_effect=round(anchor_effect, 2),
            drift_from_anchor=round(drift, 2),
        )

    def _build_concession_trajectory(self, segments: List[Dict]) -> List[ConcessionEvent]:
        """Track concessions across the negotiation timeline."""
        events = []
        for i, seg in enumerate(segments):
            concessions = seg.get("concessions_offered", [])
            if not concessions:
                continue

            speaker = seg.get("speaker", "").lower()
            party = "supplier" if ("supplier" in speaker or "account" in speaker) else "buyer"

            # Check for pricing concessions
            text = _extract_text(seg)
            prices = [
                float(m.group(1).replace(",", ""))
                for m in _PRICE_RE.finditer(text)
            ]

            for c in concessions:
                events.append(ConcessionEvent(
                    segment_index=i,
                    party=party,
                    description=c,
                    magnitude=prices[0] if prices else None,
                ))
        return events

    def _classify_concession_pattern(self, concessions: List[ConcessionEvent]) -> str:
        """Classify the overall concession pattern."""
        if not concessions:
            return "none"

        parties = [c.party for c in concessions]
        buyer_count = parties.count("buyer")
        supplier_count = parties.count("supplier")

        if buyer_count == 0 and supplier_count == 0:
            return "none"

        # Check for tit-for-tat (alternating)
        if len(parties) >= 3:
            alternating = sum(
                1 for i in range(1, len(parties)) if parties[i] != parties[i - 1]
            )
            if alternating >= len(parties) * 0.6:
                return "tit_for_tat"

        # Check for one-sided
        if buyer_count == 0 or supplier_count == 0:
            return "one_sided"

        # Check for front-loaded (most concessions in first half)
        mid = len(concessions) // 2
        first_half = len(concessions[:max(mid, 1)])
        second_half = len(concessions[max(mid, 1):])
        if first_half > second_half * 2:
            return "front_loaded"

        return "gradual"

    # -- Nash Equilibrium Approximation ----------------------------------------

    def _estimate_nash(
        self,
        zopa: ZOPAEstimate,
        intels: List[SegmentNegotiationIntel],
        all_prices: List[float],
    ) -> NashEquilibriumEstimate:
        """Approximate Nash equilibrium from revealed preferences and leverage.

        In a simplified bilateral negotiation:
        - If ZOPA exists, Nash equilibrium ≈ ZOPA midpoint adjusted by leverage
        - Leverage shifts the equilibrium toward the stronger party's preference
        """
        if not zopa.overlap or zopa.zopa_range is None:
            # No ZOPA — estimate from price trajectory
            if len(all_prices) >= 2:
                # Use convergence point of last two prices
                estimated = (all_prices[-1] + all_prices[-2]) / 2
                return NashEquilibriumEstimate(
                    estimated_agreement_point=round(estimated, 2),
                    method="price_convergence",
                    buyer_utility=0.5,
                    supplier_utility=0.5,
                    pareto_optimal=False,
                    rationale="No clear ZOPA; estimated from price trajectory convergence.",
                )
            return NashEquilibriumEstimate(
                estimated_agreement_point=None,
                method="insufficient_data",
                buyer_utility=0.0,
                supplier_utility=0.0,
                pareto_optimal=False,
                rationale="Insufficient price data to estimate equilibrium.",
            )

        floor, ceil = zopa.zopa_range
        midpoint = (floor + ceil) / 2

        # Leverage adjustment: shift toward stronger party
        avg_buyer_lev = 0.5
        avg_supplier_lev = 0.5
        if intels:
            avg_buyer_lev = sum(
                i.power_balance.buyer_leverage for i in intels
            ) / len(intels)
            avg_supplier_lev = sum(
                i.power_balance.supplier_leverage for i in intels
            ) / len(intels)

        # Shift: positive = toward buyer preference (lower price)
        leverage_diff = avg_buyer_lev - avg_supplier_lev
        zopa_width = ceil - floor
        adjustment = leverage_diff * zopa_width * 0.3  # 30% of ZOPA width max shift

        estimated = midpoint - adjustment  # buyer leverage pushes price down
        estimated = max(floor, min(ceil, estimated))  # clamp within ZOPA

        # Utility estimates (how good is this for each party?)
        if ceil > floor:
            buyer_utility = round((ceil - estimated) / (ceil - floor), 2)
            supplier_utility = round((estimated - floor) / (ceil - floor), 2)
        else:
            buyer_utility = supplier_utility = 0.5

        return NashEquilibriumEstimate(
            estimated_agreement_point=round(estimated, 2),
            method="leverage_adjusted",
            buyer_utility=buyer_utility,
            supplier_utility=supplier_utility,
            pareto_optimal=True,
            rationale=(
                f"ZOPA [{floor:.2f}–{ceil:.2f}] midpoint ${midpoint:.2f} "
                f"adjusted by leverage differential ({leverage_diff:+.2f}) "
                f"→ equilibrium at ${estimated:.2f}."
            ),
        )

    # -- Deal Health & Recommendations -----------------------------------------

    def _assess_deal_health(
        self, intels: List[SegmentNegotiationIntel], concessions: List[ConcessionEvent]
    ) -> str:
        """Is the negotiation converging, stalled, or diverging?"""
        if len(intels) < 2:
            return "converging"

        # Check escalation trend
        recent = intels[-3:] if len(intels) >= 3 else intels
        esc_count = sum(1 for i in recent if i.escalation_level == "escalating")
        deesc_count = sum(1 for i in recent if i.escalation_level == "de_escalating")

        if esc_count > deesc_count:
            return "diverging"

        # Check if concessions are flowing or dried up
        if concessions:
            last_concession_seg = max(c.segment_index for c in concessions)
            if last_concession_seg < len(intels) - 3:
                return "stalled"

        return "converging"

    def _detect_resolved_issues(self, segments: List[Dict]) -> set:
        """Detect issues that appear to be resolved (agreed upon)."""
        resolved = set()
        resolution_markers = {"agreed", "confirmed", "locked in", "done",
                              "that works", "we can do that", "accepted"}
        for seg in segments:
            text = _extract_text(seg)
            if any(m in text for m in resolution_markers):
                for issue, keywords in _ISSUE_CATEGORIES.items():
                    if any(kw in text for kw in keywords):
                        resolved.add(issue)
        return resolved

    def _identify_value_creation(
        self, segments: List[Dict], intels: List[SegmentNegotiationIntel]
    ) -> List[str]:
        """Identify opportunities for integrative (value-creating) moves."""
        opportunities: List[str] = []

        # Check for issues mentioned but not yet traded
        all_issues = set()
        for intel in intels:
            all_issues.update(intel.issues_on_table)

        if "delivery" in all_issues and "price" in all_issues:
            opportunities.append(
                "Link delivery commitments to volume tiers — "
                "faster delivery in exchange for higher minimum order"
            )
        if "relationship" in all_issues:
            opportunities.append(
                "Explore multi-year agreement for price stability — "
                "long-term commitment as leverage for better terms"
            )
        if "compliance" in all_issues and "contract_terms" in all_issues:
            opportunities.append(
                "Bundle compliance certifications into contract — "
                "reduce audit overhead in exchange for longer term"
            )
        if "sla" in all_issues and "price" in all_issues:
            opportunities.append(
                "Tiered SLA pricing — higher SLA with premium, "
                "lower SLA with reduced rate, let buyer choose"
            )

        # Generic integrative check
        for intel in intels:
            if intel.integrative_signals and not opportunities:
                opportunities.append(
                    "Both parties showing willingness to expand scope — "
                    "explore bundled service packages"
                )

        return opportunities

    def _generate_recommendations(
        self,
        zopa: ZOPAEstimate,
        nash: NashEquilibriumEstimate,
        intels: List[SegmentNegotiationIntel],
        concessions: List[ConcessionEvent],
        open_issues: List[str],
        deal_health: str,
    ) -> List[str]:
        """Generate actionable next-move recommendations."""
        recs: List[str] = []

        # ZOPA-based
        if zopa.overlap and zopa.zopa_range:
            floor, ceil = zopa.zopa_range
            if nash.estimated_agreement_point:
                target = nash.estimated_agreement_point
                recs.append(
                    f"Target ${target:.2f} — Nash equilibrium estimate "
                    f"within ZOPA [${floor:.2f}–${ceil:.2f}]"
                )

        # Power-based
        if intels:
            last_power = intels[-1].power_balance
            if last_power.dominant_party == "buyer":
                recs.append(
                    "Leverage is currently with buyer — push for additional "
                    "concessions on open issues before locking terms"
                )
            elif last_power.dominant_party == "supplier":
                recs.append(
                    "Supplier holds leverage — consider strengthening BATNA "
                    "by qualifying alternative vendors before next round"
                )

        # Open issues
        if open_issues:
            recs.append(
                f"Unresolved issues: {', '.join(open_issues)} — "
                "prioritize by impact and use as logrolling currency"
            )

        # Concession pattern
        if concessions:
            one_sided = all(c.party == concessions[0].party for c in concessions)
            if one_sided:
                non_conceding = "buyer" if concessions[0].party == "supplier" else "supplier"
                recs.append(
                    f"Concessions have been one-sided — request reciprocal "
                    f"movement from {non_conceding} to maintain fairness norm"
                )

        # Deal health
        if deal_health == "stalled":
            recs.append(
                "Negotiation appears stalled — consider reframing with "
                "new information or introducing a package deal to restart momentum"
            )
        elif deal_health == "diverging":
            recs.append(
                "Positions are diverging — de-escalate by acknowledging "
                "shared interests before revisiting contentious terms"
            )

        # BATNA
        if intels:
            last_batna = intels[-1].batna
            if last_batna.buyer_batna_strength == "none":
                recs.append(
                    "No buyer BATNA signals detected — develop alternatives "
                    "before next round to strengthen bargaining position"
                )

        return recs


# ---------------------------------------------------------------------------
# Convenience: Enrich segment data dict in-place
# ---------------------------------------------------------------------------

def enrich_segment_negotiation_intel(segment_data: Dict, segment_index: int = 0) -> Dict:
    """Convenience function to add negotiation intelligence fields to a segment dict.

    Called from ProcurementPack.extract() to add game-theory analysis
    alongside the existing keyword-based extraction.
    """
    analyzer = NegotiationAnalyzer()
    intel = analyzer.analyze_segment(segment_data, segment_index)

    segment_data["negotiation_tactics"] = [
        {"tactic": t.tactic, "confidence": t.confidence, "description": t.description}
        for t in intel.tactics_detected
    ]
    segment_data["power_balance"] = {
        "buyer_leverage": intel.power_balance.buyer_leverage,
        "supplier_leverage": intel.power_balance.supplier_leverage,
        "dominant_party": intel.power_balance.dominant_party,
        "leverage_drivers": intel.power_balance.leverage_drivers,
    }
    segment_data["batna_assessment"] = {
        "buyer_signals": intel.batna.buyer_batna_signals,
        "supplier_signals": intel.batna.supplier_batna_signals,
        "buyer_strength": intel.batna.buyer_batna_strength,
        "supplier_strength": intel.batna.supplier_batna_strength,
    }
    segment_data["escalation_level"] = intel.escalation_level
    segment_data["bargaining_style"] = intel.bargaining_style
    segment_data["issues_on_table"] = intel.issues_on_table
    segment_data["integrative_signals"] = intel.integrative_signals
    segment_data["distributive_signals"] = intel.distributive_signals

    return segment_data


def generate_session_report(segments: List[Dict]) -> Dict:
    """Generate a full negotiation intelligence report for a session.

    Called after all segments have been processed. Returns a dict suitable
    for storage / API response.
    """
    analyzer = NegotiationAnalyzer()
    report = analyzer.analyze_session(segments)
    return report.to_dict()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(segment_data: Dict) -> str:
    """Build searchable text from all available segment fields."""
    parts = [
        segment_data.get("topic", ""),
        segment_data.get("transcript", ""),
        " ".join(segment_data.get("objections", [])),
        " ".join(segment_data.get("decision_signals", [])),
        segment_data.get("speaker", ""),
    ]
    return " ".join(parts).lower()
