"""Knowledge Graph — entity relationship graph over the video library.

Entities extracted from video segments (people, companies, products,
features, competitors, prices, dates) are stored as nodes.  Co-occurrence
in the same segment creates edges.

Built on collections.defaultdict — no NetworkX required, though NetworkX
graph export is provided when available.
"""
from __future__ import annotations

import collections
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Entity extraction patterns ────────────────────────────────────────────────
# Combine keyword matching with regex-based NER for richer extraction.

_KEYWORD_PATTERNS: List[Tuple[str, str]] = [
    ("pricing", "topic"), ("discount", "topic"), ("contract", "topic"),
    ("demo", "topic"), ("pilot", "topic"), ("poc", "topic"),
    ("integration", "topic"), ("onboarding", "topic"),
    ("budget", "topic"), ("timeline", "topic"), ("security", "topic"),
    ("compliance", "topic"), ("migration", "topic"), ("support", "topic"),
    ("roi", "topic"), ("implementation", "topic"), ("deployment", "topic"),
    ("competitor", "competitor"), ("alternative", "competitor"),
    ("salesforce", "competitor"), ("hubspot", "competitor"),
    ("gong", "competitor"), ("chorus", "competitor"), ("clari", "competitor"),
    ("zoom", "product"), ("slack", "product"), ("teams", "product"),
    ("deadline", "temporal"), ("q1", "temporal"), ("q2", "temporal"),
    ("q3", "temporal"), ("q4", "temporal"), ("next quarter", "temporal"),
    ("next month", "temporal"), ("this year", "temporal"), ("end of year", "temporal"),
]

import re

# Regex patterns for richer entity extraction
_MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?(?:\s*[KkMmBb])?|\d+(?:,\d{3})*\s*(?:dollars|USD)", re.I)
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_ORG_SUFFIXES_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Inc|Corp|LLC|Ltd|Co|Group|Solutions|Technologies|Software|Systems|Networks|Labs|Analytics))\b"
)
_PERSON_RE = re.compile(
    r"\b((?:Mr|Mrs|Ms|Dr|CEO|CTO|VP|Director|Manager|Head)\s*\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)
_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
)


def _extract_entities(text: str) -> List[Tuple[str, str]]:
    """Multi-strategy entity extraction: keywords + regex NER."""
    found: List[Tuple[str, str]] = []
    lower = text.lower()

    # Keyword matches
    for kw, etype in _KEYWORD_PATTERNS:
        if kw in lower:
            found.append((kw, etype))

    # Money amounts
    for m in _MONEY_RE.findall(text):
        found.append((m.strip(), "money"))

    # Percentages (often discounts, growth figures)
    for m in _PERCENT_RE.findall(text):
        found.append((m, "metric"))

    # Email addresses
    for m in _EMAIL_RE.findall(text):
        found.append((m, "email"))

    # Organization names
    for m in _ORG_SUFFIXES_RE.findall(text):
        found.append((m.strip(), "organization"))

    # Person names (title-prefixed)
    for m in _PERSON_RE.findall(text):
        found.append((m.strip(), "person"))

    # Dates
    for m in _DATE_RE.findall(text):
        found.append((m.strip(), "date"))

    return found


@dataclass
class KGNode:
    id: str
    entity_type: str
    label: str
    jobs: Set[str] = field(default_factory=set)
    frequency: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.entity_type,
            "label": self.label,
            "frequency": self.frequency,
            "jobs": sorted(self.jobs),
        }


@dataclass
class KGEdge:
    source: str       # node id
    target: str       # node id
    weight: int = 1   # co-occurrence count

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "target": self.target, "weight": self.weight}


class KnowledgeGraph:
    """In-memory entity co-occurrence graph built from video extractions."""

    def __init__(self) -> None:
        self._nodes: Dict[str, KGNode] = {}
        self._edges: Dict[Tuple[str, str], KGEdge] = {}

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def add_video(self, job_id: str, intel: Dict[str, Any]) -> int:
        """Index entities from all segments of a job. Returns entity count."""
        segments = intel.get("segments", [])
        entity_count = 0
        for seg in segments:
            ext = seg.get("extraction", seg)
            text_parts = [
                ext.get("topic", ""),
                " ".join(ext.get("objections", [])),
                " ".join(ext.get("decision_signals", [])),
                seg.get("transcript", ""),
            ]
            combined = " ".join(text_parts)

            # Extract entities + named items from extraction fields
            entities: List[Tuple[str, str]] = _extract_entities(combined)

            # Topics as entities
            topic = ext.get("topic", "general")
            entities.append((topic, "topic"))

            # Objections as entities
            for obj in ext.get("objections", [])[:3]:
                entities.append((obj.lower().strip()[:40], "objection"))

            entity_nodes: List[str] = []
            for entity, etype in entities:
                nid = f"{etype}:{entity}"
                if nid not in self._nodes:
                    self._nodes[nid] = KGNode(id=nid, entity_type=etype, label=entity)
                self._nodes[nid].jobs.add(job_id)
                self._nodes[nid].frequency += 1
                entity_nodes.append(nid)
                entity_count += 1

            # Create edges between all entity pairs in this segment
            for i, a in enumerate(entity_nodes):
                for b in entity_nodes[i + 1:]:
                    if a == b:
                        continue
                    edge_key = (min(a, b), max(a, b))
                    if edge_key not in self._edges:
                        self._edges[edge_key] = KGEdge(source=edge_key[0], target=edge_key[1])
                    else:
                        self._edges[edge_key].weight += 1

        return entity_count

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, entity: str, limit: int = 20) -> Dict[str, Any]:
        """Find nodes matching entity label and their top connected nodes."""
        lower = entity.lower()
        matching = [n for n in self._nodes.values() if lower in n.label.lower()]
        if not matching:
            return {"nodes": [], "edges": [], "query": entity}

        node_ids = {n.id for n in matching[:limit]}
        # Expand with 1-hop neighbours
        related_edges = [
            e for e in self._edges.values()
            if e.source in node_ids or e.target in node_ids
        ]
        neighbour_ids = {
            e.source for e in related_edges
        } | {e.target for e in related_edges}

        all_node_ids = node_ids | neighbour_ids
        nodes = [self._nodes[nid].to_dict() for nid in all_node_ids if nid in self._nodes]
        edges = [e.to_dict() for e in related_edges]
        return {"nodes": nodes, "edges": edges, "query": entity}

    def get_relationships(self, entity: str) -> List[Dict[str, Any]]:
        lower = entity.lower()
        matching_ids = {n.id for n in self._nodes.values() if lower in n.label.lower()}
        edges = [
            e.to_dict() for e in self._edges.values()
            if e.source in matching_ids or e.target in matching_ids
        ]
        return sorted(edges, key=lambda x: -x["weight"])

    def top_entities(self, entity_type: Optional[str] = None,
                     limit: int = 20) -> List[Dict[str, Any]]:
        nodes = [n for n in self._nodes.values()
                 if entity_type is None or n.entity_type == entity_type]
        return [n.to_dict() for n in sorted(nodes, key=lambda x: -x.frequency)[:limit]]

    def export_json(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "stats": {
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
            },
        }

    def export_networkx(self):  # type: ignore[return]
        """Export to NetworkX MultiGraph if networkx is installed."""
        import networkx as nx  # optional dep
        G = nx.Graph()
        for n in self._nodes.values():
            G.add_node(n.id, label=n.label, entity_type=n.entity_type, frequency=n.frequency)
        for e in self._edges.values():
            G.add_edge(e.source, e.target, weight=e.weight)
        return G

    @property
    def stats(self) -> Dict[str, int]:
        return {"nodes": len(self._nodes), "edges": len(self._edges)}


_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph
