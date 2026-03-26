"""Schema registry — store, retrieve, and manage custom extraction schemas.

Schemas are persisted as JSON files in TEMPORALOS_SCHEMAS_DIR.
Each schema defines fields that a SchemaBasedExtractor will extract.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

SCHEMAS_DIR = Path(os.environ.get("TEMPORALOS_SCHEMAS_DIR", "/tmp/temporalos/schemas"))


class FieldType(str, Enum):
    STRING = "string"           # free text
    CATEGORY = "category"       # one-of (from options list)
    BOOLEAN = "boolean"         # true/false
    NUMBER = "number"           # float
    LIST_STRING = "list_string" # list of strings
    LIST_CATEGORY = "list_category"
    JSON = "json"               # nested object / dict


@dataclass
class FieldDefinition:
    name: str
    type: FieldType
    description: str
    required: bool = True
    options: List[str] = field(default_factory=list)   # for CATEGORY / LIST_CATEGORY
    default: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "required": self.required,
            "options": self.options,
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FieldDefinition":
        return cls(
            name=d["name"],
            type=FieldType(d["type"]),
            description=d["description"],
            required=d.get("required", True),
            options=d.get("options", []),
            default=d.get("default"),
        )


@dataclass
class SchemaDefinition:
    id: str
    name: str
    description: str
    fields: List[FieldDefinition]
    vertical: str = "custom"       # sales | ux_research | cs | real_estate | custom
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "vertical": self.vertical,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SchemaDefinition":
        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            fields=[FieldDefinition.from_dict(f) for f in d.get("fields", [])],
            vertical=d.get("vertical", "custom"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


class SchemaRegistry:
    """File-backed schema registry."""

    def __init__(self, schemas_dir: Path = SCHEMAS_DIR):
        self.schemas_dir = schemas_dir
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, description: str, fields: List[FieldDefinition],
               vertical: str = "custom") -> SchemaDefinition:
        schema = SchemaDefinition(
            id=uuid.uuid4().hex,
            name=name,
            description=description,
            fields=fields,
            vertical=vertical,
        )
        self._save(schema)
        return schema

    def get(self, schema_id: str) -> Optional[SchemaDefinition]:
        path = self.schemas_dir / f"{schema_id}.json"
        if not path.exists():
            return None
        return SchemaDefinition.from_dict(json.loads(path.read_text()))

    def list(self, vertical: Optional[str] = None) -> List[SchemaDefinition]:
        schemas = []
        for f in sorted(self.schemas_dir.glob("*.json")):
            try:
                s = SchemaDefinition.from_dict(json.loads(f.read_text()))
                if vertical is None or s.vertical == vertical:
                    schemas.append(s)
            except Exception:
                pass
        return schemas

    def delete(self, schema_id: str) -> bool:
        path = self.schemas_dir / f"{schema_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def update(self, schema_id: str, **kwargs) -> Optional[SchemaDefinition]:
        schema = self.get(schema_id)
        if schema is None:
            return None
        for k, v in kwargs.items():
            if hasattr(schema, k):
                setattr(schema, k, v)
        schema.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(schema)
        return schema

    def _save(self, schema: SchemaDefinition) -> None:
        path = self.schemas_dir / f"{schema.id}.json"
        path.write_text(json.dumps(schema.to_dict(), indent=2))


_registry: Optional[SchemaRegistry] = None


def get_schema_registry() -> SchemaRegistry:
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry
