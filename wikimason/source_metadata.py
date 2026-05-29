"""Source metadata helpers: wm_ fields, sidecar I/O, MIME/hash utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .constants import SOURCE_SCHEMA_VERSION
from .frontmatter import update_frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_REQUIRED_FIELDS = {
    # identity
    "schema_version",
    "source_id",
    "path",
    "original_filename",
    # hashes
    "content_sha256",
    "body_sha256",
    "metadata_sha256",
    "size_bytes",
    # metadata
    "source_kind",
    "mime_type",
    "hash_algorithm",
    "hash_scope",
    # lifecycle
    "first_seen_at",
    "last_scanned_at",
    # coverage
    "covered_sha256",
    "covered_body_sha256",
    "covered_metadata_sha256",
    "coverage",
    "coverage_status",
    # presence
    "present",
    "removed_at",
}

# Legacy fields that were split out in old schema
_LEGACY_EXTRA_FIELDS = {
    "sha256",
    "source_title",
    "author",
    "reference",
    "created",
    "processed",
}

# ---------------------------------------------------------------------------
# Field construction
# ---------------------------------------------------------------------------

WIKIMASON_KIND = "raw-source"
WIKIMASON_VERSION = SOURCE_SCHEMA_VERSION
ACCEPTED_WM_KINDS = {"raw-source", "wikimason_source"}


def manifest_required_fields() -> set[str]:
    return set(SOURCE_REQUIRED_FIELDS)


def generate_source_id(content: str, timestamp: datetime | None = None) -> str:
    ts = timestamp or datetime.now(timezone.utc)
    prefix = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"src_{ts.strftime('%Y%m%d')}_{prefix}"


def _build_wm_fields(
    *,
    source_id: str,
    captured_at: str,
    original_filename: str,
    current_filename: str,
    source_kind: str = "text",
    mime_type: str = "text/markdown",
    byte_size: int = 0,
    content_sha256: str = "",
    hash_algorithm: str = "sha256",
    hash_scope: str = "body_without_frontmatter",
    **extra: object,
) -> dict[str, object]:
    """Build ``wm_``-prefixed fields dict for frontmatter embedding."""
    fields: dict[str, object] = {
        "wm_kind": WIKIMASON_KIND,
        "wm_schema_version": WIKIMASON_VERSION,
        "wm_source_id": source_id,
        "wm_captured_at": captured_at,
        "wm_original_filename": original_filename,
        "wm_current_filename": current_filename,
        "wm_source_kind": source_kind,
        "wm_mime_type": mime_type,
        "wm_byte_size": byte_size,
        "wm_hash_algorithm": hash_algorithm,
        "wm_hash_scope": hash_scope,
        "wm_content_sha256": content_sha256,
    }
    fields.update(extra)
    return fields


def embed_wikimason_metadata(text: str, fields: dict[str, object]) -> str:
    """Embed ``wm_``-prefixed fields into the frontmatter of *text*.

    Each field becomes a separate frontmatter key, which round-trips
    through the simple frontmatter parser without needing nested YAML.
    """
    return update_frontmatter(text, fields)


def extract_wikimason_metadata(metadata: dict[str, object]) -> dict[str, object] | None:
    """Return ``wm_``-prefixed fields from *metadata*, or None."""
    result: dict[str, object] = {}
    for key, value in metadata.items():
        if key.startswith("wm_"):
            result[key] = value
    return result if result else None


def raw_source_fields(data: dict[str, object]) -> dict[str, object]:
    """Extract legacy display fields from frontmatter (backward compat)."""
    return {
        "source_title": str(data.get("Title") or data.get("title") or ""),
        "author": str(data.get("Author") or ""),
        "reference": str(data.get("Reference") or ""),
        "created": str(data.get("Created") or data.get("created") or ""),
        "processed": bool(data.get("Processed", False)),
    }


# ---------------------------------------------------------------------------
# Binary sidecar helpers
# ---------------------------------------------------------------------------
SIDECAR_SUFFIX = ".wikimason.json"
LEGACY_SIDECAR_SUFFIX = ".wikimason.yml"


def sidecar_path(source_path: Path) -> Path:
    """Return the sidecar path for a binary source."""
    return source_path.with_name(source_path.name + SIDECAR_SUFFIX)


def is_binary_source(path: Path) -> bool:
    """Heuristic: non-md files are treated as binary."""
    return path.suffix.lower() != ".md"


def read_sidecar(sidecar: Path) -> dict[str, object] | None:
    """Read a JSON sidecar, falling back to legacy YAML."""
    if not sidecar.exists():
        # Try legacy .yml sidecar
        legacy = sidecar.with_name(
            sidecar.name.replace(SIDECAR_SUFFIX, LEGACY_SIDECAR_SUFFIX)
        )
        if legacy.exists():
            import yaml

            with legacy.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                return data
        return None
    with sidecar.open(encoding="utf-8") as fh:
        data = json.loads(fh.read())
    if isinstance(data, dict):
        return data
    return None


def write_sidecar(sidecar: Path, block: dict[str, object]) -> None:
    """Write a JSON sidecar with the wikimason block."""
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(block, sort_keys=True, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# MIME / hash / time utilities
# ---------------------------------------------------------------------------


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".html": "text/html",
        ".json": "application/json",
        ".csv": "text/csv",
    }
    return mime_map.get(suffix, "application/octet-stream")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
