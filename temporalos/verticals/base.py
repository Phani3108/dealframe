"""Base class for vertical packs."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition

logger = logging.getLogger(__name__)


class VerticalPack(ABC):
    """A vertical pack bundles a schema, summary type preference, extraction
    logic, and metadata."""

    id: str = ""
    name: str = ""
    description: str = ""
    industries: List[str] = []
    summary_type: str = "meeting_notes"
    # Set to False in a subclass to opt out of automatic negotiation enrichment.
    enrich_with_negotiation_intel: bool = True

    @abstractmethod
    def schema(self) -> SchemaDefinition:
        """Return the SchemaDefinition for this vertical."""
        ...

    def _vertical_extract(self, segment_data: Dict) -> Dict:
        """Override in subclasses to add vertical-specific fields.

        The default implementation is a no-op (returns the dict unchanged).
        Do NOT call super() in subclasses — the base class calls this via
        :meth:`extract` and then applies shared enrichments afterward.
        """
        return segment_data

    def extract(self, segment_data: Dict) -> Dict:
        """Apply vertical-specific extraction then shared enrichments.

        Subclasses should override :meth:`_vertical_extract`, not this method.
        This ensures the negotiation intelligence layer runs for every vertical.
        """
        # 1. Vertical-specific logic
        enriched = self._vertical_extract(segment_data)

        # 2. Negotiation intelligence (shared across all verticals)
        if self.enrich_with_negotiation_intel:
            try:
                from temporalos.intelligence.negotiation import enrich_segment_negotiation_intel
                enriched = enrich_segment_negotiation_intel(enriched)
            except Exception as exc:
                logger.debug("Negotiation enrichment skipped: %s", exc)

        return enriched

    def to_dict(self) -> dict:
        schema_dict = self.schema().to_dict()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "industries": self.industries,
            "summary_type": self.summary_type,
            "field_count": len(schema_dict["fields"]),
            "fields": schema_dict["fields"],
        }


class VerticalPackRegistry:
    def __init__(self) -> None:
        self._packs: Dict[str, VerticalPack] = {}

    def register(self, pack: VerticalPack) -> None:
        self._packs[pack.id] = pack

    def get(self, pack_id: str) -> Optional[VerticalPack]:
        return self._packs.get(pack_id)

    def list(self) -> List[VerticalPack]:
        return list(self._packs.values())

    def list_packs(self) -> List[VerticalPack]:
        return list(self._packs.values())

    def list_ids(self) -> List[str]:
        return list(self._packs.keys())


def get_vertical_registry() -> VerticalPackRegistry:
    from temporalos.verticals import get_default_vertical_registry
    return get_default_vertical_registry()
