"""Source lifecycle: re-export facade.

All implementation lives in the split source modules:
  - source_metadata.py  -- wm_ fields, sidecar I/O, MIME/hash utilities
  - source_manifest.py  -- manifest load/write
  - source_scan.py      -- scan, record construction, source_add, source_resolve
  - source_delta.py     -- delta, coverage report
  - source_verify.py    -- verify, rehash, frontmatter migration, lint
"""

from __future__ import annotations

# Delta
from .source_delta import (
    source_coverage,
    source_coverage_report,
    source_delta,
)

# Manifest
from .source_manifest import (
    load_source_manifest,
    write_source_manifest,
)

# Metadata
from .source_metadata import (
    _LEGACY_EXTRA_FIELDS,
    ACCEPTED_WM_KINDS,
    LEGACY_SIDECAR_SUFFIX,
    SIDECAR_SUFFIX,
    SOURCE_REQUIRED_FIELDS,
    WIKIMASON_KIND,
    WIKIMASON_VERSION,
    _build_wm_fields,
    _guess_mime,
    embed_wikimason_metadata,
    extract_wikimason_metadata,
    generate_source_id,
    is_binary_source,
    manifest_required_fields,
    now_iso,
    raw_source_fields,
    read_sidecar,
    sha256_text,
    sidecar_path,
    write_sidecar,
)

# Scan
from .source_scan import (
    build_source_coverage_map,
    raw_record,
    source_add,
    source_resolve_report,
    source_scan,
    source_scan_payload,
)

# Verify
from .source_verify import (
    source_lint,
    source_migrate_frontmatter,
    source_rehash,
    source_verify,
)

__all__ = [
    "WIKIMASON_KIND",
    "WIKIMASON_VERSION",
    "ACCEPTED_WM_KINDS",
    "SIDECAR_SUFFIX",
    "LEGACY_SIDECAR_SUFFIX",
    "SOURCE_REQUIRED_FIELDS",
    "_LEGACY_EXTRA_FIELDS",
    "_build_wm_fields",
    "_guess_mime",
    "build_source_coverage_map",
    "embed_wikimason_metadata",
    "extract_wikimason_metadata",
    "generate_source_id",
    "is_binary_source",
    "load_source_manifest",
    "manifest_required_fields",
    "now_iso",
    "raw_record",
    "raw_source_fields",
    "read_sidecar",
    "sha256_text",
    "sidecar_path",
    "source_add",
    "source_coverage",
    "source_coverage_report",
    "source_delta",
    "source_lint",
    "source_migrate_frontmatter",
    "source_rehash",
    "source_resolve_report",
    "source_scan",
    "source_scan_payload",
    "source_verify",
    "write_sidecar",
    "write_source_manifest",
]
