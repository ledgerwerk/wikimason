"""Atomic text-write wrappers backed by ledgercore.

WikiMason routes high-value generated/rewritten-file writes through these
wrappers so that interruptions cannot leave truncated or partially-written
files. The wrappers are byte-preserving relative to ``Path.write_text(text,
encoding="utf-8")``: they intentionally do NOT normalize newlines, so user
content (e.g. CRLF sources) is not silently rewritten.

Append-oriented writes with rotation (``logs.py``) are intentionally NOT
served here; ledgercore currently provides atomic full-file writes only.
"""

from __future__ import annotations

from pathlib import Path

from ledgercore.atomic import atomic_create_text, atomic_write_text

__all__ = ["write_text_atomic", "create_text_atomic"]


def write_text_atomic(path: Path, text: str) -> None:
    """Atomically overwrite *path* with *text* (UTF-8, newline-preserving).

    Creates parent directories as needed. Use for generated files, manifests,
    catalogs, sidecars, AGENTS.md, and note/link normalization rewrites.
    """
    # normalize=False keeps bytes identical to Path.write_text(...); the value
    # of atomicity here is crash-safety, not newline rewriting.
    atomic_write_text(path, text, normalize=False)


def create_text_atomic(path: Path, text: str) -> None:
    """Atomically create *path* with *text*, failing if it already exists.

    Use for "create new" semantics where clobbering an existing file would be
    a bug (e.g. new note creation that should refuse to overwrite).
    """
    atomic_create_text(path, text)
