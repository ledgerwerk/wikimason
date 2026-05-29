from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .commands import (
    render_agent_workflow_markdown,
    render_command_reference_markdown,
    render_policy_markdown,
)
from .config import WikiMasonConfig, load_runtime_config
from .profiles import supported_profiles
from .schema import load_vault_schema, schema_generated_paths, schema_source_label

# Regex to find the manual section in existing AGENTS.md
MANUAL_BLOCK_RE = re.compile(
    r"<!--\s*WIKIMASON:MANUAL\s+BEGIN\s*-->(.*?)<!--\s*WIKIMASON:MANUAL\s+END\s*-->",
    re.DOTALL,
)

# Legacy marker support
_LEGACY_MANUAL_BLOCK_RE = re.compile(
    r"<!-- wikimason:manual:start -->.*?<!-- wikimason:manual:end -->",
    re.DOTALL,
)


def agents_sources(vault: Path, *, config: WikiMasonConfig | None = None) -> list[Path]:
    active_config = config or load_runtime_config(vault)
    schema_dir = vault / active_config.paths.schema
    templates_dir = vault / active_config.paths.templates
    candidates = [
        schema_dir / "agent-workflow.md",
        schema_dir / "policy.md",
        schema_dir / "purpose.md",
        schema_dir / "l1-policy.md",
        *(sorted(templates_dir.glob("*.md"))),
    ]
    if active_config.source_path is not None:
        candidates.insert(0, active_config.source_path)
    else:
        legacy_schema = vault / "Schema/wikimason.json"
        candidates.insert(0, legacy_schema)
    return [path for path in candidates if path.exists()]


def compute_input_hashes(
    vault: Path, *, config: WikiMasonConfig | None = None
) -> dict[str, str]:
    """Compute sha256 hashes for all AGENTS input files.

    Returns a dict mapping relative paths to their sha256 hex digests.
    """
    active_config = config or load_runtime_config(vault)
    hashes: dict[str, str] = {}
    for path in agents_sources(vault, config=active_config):
        try:
            rel = path.relative_to(vault).as_posix()
            content = path.read_bytes()
            h = hashlib.sha256(content).hexdigest()
            hashes[rel] = h
        except (OSError, ValueError):
            pass
    # Also hash the config file if it exists
    if active_config.source_path and active_config.source_path.exists():
        try:
            rel = active_config.source_path.relative_to(vault).as_posix()
            content = active_config.source_path.read_bytes()
            hashes[rel] = hashlib.sha256(content).hexdigest()
        except (OSError, ValueError):
            pass
    return hashes


def _render_input_hashes_block(hashes: dict[str, str]) -> str:
    """Render input hashes as an indented YAML-like block inside the HTML comment."""
    lines = ["  input_hashes:"]
    for path, h in sorted(hashes.items()):
        lines.append(f"    {path}: sha256:{h}")
    return "\n".join(lines)


def _build_generated_header(
    vault: Path, *, config: WikiMasonConfig | None = None
) -> str:
    """Build the generated header comment with metadata and input hashes."""
    active_config = config or load_runtime_config(vault)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    hashes = compute_input_hashes(vault, config=active_config)
    lines = [
        "<!--",
        "  generated_by: wikimason agents compile",
        f"  generated_at: {now}",
        f"  profile: {active_config.profile}",
        _render_input_hashes_block(hashes),
        "  manual_edits: preserve between WIKIMASON:MANUAL BEGIN/END markers only",
        "-->",
    ]
    return "\n".join(lines)


def compile_agents_md(vault: Path, *, config: WikiMasonConfig | None = None) -> str:
    active_config = config or load_runtime_config(vault)
    schema = load_vault_schema(vault, config=active_config)
    agents_path = vault / active_config.paths.agents
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    manual = _manual_block(existing) or _legacy_manual_block(existing)
    schema_dir = vault / active_config.paths.schema
    templates_dir = vault / active_config.paths.templates
    workflow = _read_or_default(
        schema_dir / "agent-workflow.md", render_agent_workflow_markdown()
    ).strip()
    policy = _read_or_default(
        schema_dir / "policy.md", render_policy_markdown()
    ).strip()

    purpose_text = _read_or_default(schema_dir / "purpose.md", "").strip()
    l1_policy_text = _read_or_default(schema_dir / "l1-policy.md", "").strip()

    header = _build_generated_header(vault, config=active_config)
    lines = [
        header,
        "",
        workflow,
        "",
        policy,
        "",
    ]
    if purpose_text:
        lines.extend([purpose_text, ""])
    if l1_policy_text:
        lines.extend([l1_policy_text, ""])
    lines.extend(
        [
            "## Wiki Context Summary",
            "",
            f"- Profile: `{active_config.profile}`",
            f"- Link style: `{active_config.links.style}`",
            f"- Config source: `{schema_source_label(vault, config=active_config)}`",
            "",
            "### Resolved paths",
            "",
            *[
                f"- `{name}` -> `{value}`"
                for name, value in active_config.paths.as_dict().items()
            ],
            "",
            "### Note kinds",
            "",
        ]
    )
    for name, note_config in schema.note_kinds.items():
        lines.append(
            f"- `{name}` -> `{note_config.folder}` using `{note_config.template}`"
            f" (required sections: {', '.join(note_config.required_sections)})"
        )
    lines.extend(
        [
            "",
            "### Allowed statuses",
            "",
            *[f"- `{status}`" for status in schema.statuses.allowed],
            "",
            "### Generated files",
            "",
            *[f"- `{path}`" for path in sorted(schema_generated_paths(schema))],
            "",
            "### Template catalog",
            "",
        ]
    )
    templates = sorted(templates_dir.glob("*.md"))
    if templates:
        lines.extend(f"- `{path.name}`" for path in templates)
    else:
        lines.append("- (none)")
    if manual:
        lines.extend(["", manual.strip(), ""])
    lines.extend(
        [
            "## Canonical Command Reference",
            "",
            render_command_reference_markdown().strip(),
            "",
            "## Profile Reference",
            "",
            _render_profile_reference(active_config).strip(),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_agents_md(
    vault: Path, force: bool = False, *, config: WikiMasonConfig | None = None
) -> Path:
    active_config = config or load_runtime_config(vault)
    target = vault / active_config.paths.agents
    compiled = compile_agents_md(vault, config=active_config)
    if force or not target.exists() or target.read_text(encoding="utf-8") != compiled:
        target.write_text(compiled, encoding="utf-8")
    return target


def _render_profile_reference(config: WikiMasonConfig) -> str:
    profiles = supported_profiles()
    lines = [
        f"Active profile: `{config.profile}`.",
        f"Supported profiles: {', '.join(f'`{p}`' for p in profiles)}.",
        "",
        "Each profile adapts the shared wiki model to a specific tool layout:",
    ]
    profile_descriptions = {
        "markdown": "Generic Markdown wiki with YAML frontmatter and nested directories.",  # noqa: E501
        "obsidian": "Obsidian-compatible vault with YAML frontmatter and wikilinks.",
        "logseq": "Logseq graph with flat pages/ directory, property:: metadata, and outliner blocks.",  # noqa: E501
    }
    for p in profiles:
        desc = profile_descriptions.get(p, "")
        active = " (active)" if p == config.profile else ""
        lines.append(f"- `{p}`{active}: {desc}")
    lines.extend(
        [
            "",
            "Filesystem operations are local and deterministic.",
        ]
    )
    return "\n".join(lines)


def _manual_block(text: str) -> str:
    match = MANUAL_BLOCK_RE.search(text)
    if match:
        return match.group(0)
    return ""


def _legacy_manual_block(text: str) -> str:
    match = _LEGACY_MANUAL_BLOCK_RE.search(text)
    return match.group(0) if match else ""


def _read_or_default(path: Path, default: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return default
