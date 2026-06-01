from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .agents import write_agents_md
from .commands import (
    render_agent_workflow_markdown,
    render_command_reference_markdown,
    render_policy_markdown,
)
from .config import default_config, env_config_path, write_config_file
from .link_format import format_link
from .page_profiles import logical_ref_to_relpath, render_page_text
from .profiles import canonical_profile_name
from .schema import (
    default_schema,
    render_frontmatter_schema_markdown,
    schema_toml_lines,
)
from .templates import (
    CONCEPT_TEMPLATE,
    ENTITY_TEMPLATE,
    LOG_TEMPLATE,
    PROJECT_TEMPLATE,
    SOURCE_TEMPLATE,
    TOPIC_TEMPLATE,
)

BASE_GITIGNORE_BLOCK = """# >>> wikimason >>>
.DS_Store
Thumbs.db
.env
.env.*
!.env.example

# Large or private raw attachments
Raw/Files/*
!Raw/Files/.gitkeep

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
dist/
build/
*.egg-info/
.venv/
# <<< wikimason <<<
"""

OBSIDIAN_GITIGNORE_BLOCK = """# Obsidian local state
.obsidian/workspace*.json
.obsidian/cache/
.obsidian/logs/
.obsidian/plugins/

"""

WELCOME_TEMPLATE = """# Welcome

Use `wikimason vault maintain` for regular maintenance.
"""

SCHEMA_DOCS = {
    "lint-checklist.md": (
        "# Lint Checklist\n\n"
        "- required frontmatter fields\n"
        "- resolved links\n"
        "- source_count parity\n"
    ),
    "naming-conventions.md": (
        "# Naming Conventions\n\nUse lowercase kebab-case filenames.\n"
    ),
    "workflow-examples.md": (
        "# Workflow Examples\n\n"
        "1. wikimason init markdown .\n"
        "2. wikimason source scan --update --accept-covered\n"
        "3. wikimason source delta\n"
        "4. wikimason index build\n"
        "5. wikimason vault lint\n"
    ),
}

CORE_KEEP_FILES = [
    "Raw/Sources/.gitkeep",
    "Raw/Files/.gitkeep",
    "Wiki/Topics/.gitkeep",
    "Wiki/Concepts/.gitkeep",
    "Wiki/Entities/.gitkeep",
    "Wiki/Projects/.gitkeep",
    "Wiki/Logs/.gitkeep",
    "_templates/.gitkeep",
]

CORE_EMPTY_FILES = {
    "Schema/source-manifest.jsonl": "",
    "Wiki/catalog.jsonl": "",
    "Wiki/log.md": "# Wiki Log\n\n",
}

SECTION_INDEX_PLACEHOLDERS = {
    "Wiki/Topics/index.md": (
        "# Topic Index\n\nTopic notes will appear here after `wikimason index build`.\n"
    ),
    "Wiki/Concepts/index.md": (
        "# Concept Index\n\n"
        "Concept notes will appear here after `wikimason index build`.\n"
    ),
    "Wiki/Entities/index.md": (
        "# Entity Index\n\n"
        "Entity notes will appear here after `wikimason index build`.\n"
    ),
    "Wiki/Projects/index.md": (
        "# Project Index\n\n"
        "Project notes will appear here after `wikimason index build`.\n"
    ),
    "Wiki/Logs/index.md": (
        "# Log Index\n\n"
        "Operational log notes will appear here after `wikimason index build`.\n"
    ),
}


def init_vault(
    vault: Path,
    demo: bool = False,
    *,
    profile: str | None = None,
    tool: str | None = None,
    env: str | None = None,
) -> None:
    active_profile = canonical_profile_name(profile or tool or "markdown")
    config = default_config(active_profile, vault)
    schema = default_schema()
    folders = [
        config.paths.sources,
        config.paths.files,
        "Wiki",
        config.profile_config.pages_dir,
        config.paths.schema,
        config.paths.templates,
        ".githooks",
    ]
    if not config.profile_config.flat_pages:
        folders.extend(
            [
                "Wiki/Topics",
                "Wiki/Concepts",
                "Wiki/Entities",
                "Wiki/Projects",
                "Wiki/Logs",
            ]
        )
    if config.tool_config.create_dot_dir:
        folders.insert(0, ".obsidian")
    for folder in folders:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    _seed_missing_core_files(vault, config)
    _write_config_if_missing(vault / "wikimason.toml", config, schema)
    if env:
        _write_config_if_missing(
            env_config_path(env),
            default_config(active_profile, vault, name=env),
            schema,
        )
    _write_if_missing(vault / "Welcome.md", WELCOME_TEMPLATE)
    _write_if_missing(vault / "_templates/source-note.md", SOURCE_TEMPLATE)
    _write_if_missing(vault / "_templates/topic-note.md", TOPIC_TEMPLATE)
    _write_if_missing(vault / "_templates/concept-note.md", CONCEPT_TEMPLATE)
    _write_if_missing(vault / "_templates/entity-note.md", ENTITY_TEMPLATE)
    _write_if_missing(vault / "_templates/project-note.md", PROJECT_TEMPLATE)
    _write_if_missing(vault / "_templates/log-note.md", LOG_TEMPLATE)
    _write_if_missing(
        vault / "Schema/frontmatter-schema.md",
        render_frontmatter_schema_markdown(schema, source_label="wikimason.toml"),
    )
    _write_if_missing(
        vault / "Schema/command-reference.md",
        render_command_reference_markdown(),
    )
    _write_if_missing(
        vault / "Schema/agent-workflow.md",
        render_agent_workflow_markdown(),
    )
    _write_if_missing(vault / "Schema/policy.md", render_policy_markdown())
    _write_if_missing(vault / "Schema/purpose.md", PURPOSE_MD)
    _write_if_missing(vault / "Schema/l1-policy.md", L1_POLICY_MD)
    from .review import seed_review_queue

    seed_review_queue(vault)
    for filename, content in SCHEMA_DOCS.items():
        _write_if_missing(vault / "Schema" / filename, content)
    if not (vault / "AGENTS.md").exists():
        write_agents_md(vault, config=config)
    _write_if_missing(
        vault / ".githooks/pre-commit",
        "#!/usr/bin/env bash\nwikimason vault maintain\n",
    )
    _append_gitignore(vault, include_obsidian=config.tool_config.create_dot_dir)
    if demo:
        _create_demo(vault, config)
        from .build import build_vault
        from .sources import source_scan

        build_vault(vault)
        source_scan(vault, update=True, accept_covered=True)


def _write_config_if_missing(path: Path, config: Any, schema: Any) -> None:
    if path.exists():
        return
    root_value = "." if path.parent == config.root else str(config.root)
    write_config_file(path, config, root_value=root_value)
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n"
        + "\n".join(schema_toml_lines(schema))
        + "\n",
        encoding="utf-8",
    )


def _create_demo(vault: Path, config: Any) -> None:
    today = date.today().isoformat()
    (vault / "Raw/Sources/wikimason-demo-source.md").write_text(
        SOURCE_TEMPLATE.format(title="LLM Wiki Demo Source", date=today),
        encoding="utf-8",
    )
    _write_demo_page(
        vault,
        config,
        logical_ref="Wiki/Concepts/compiled-knowledge",
        metadata={
            "tags": ["concept"],
            "topics": ["Wiki/Topics/wikimason.md"],
            "status": "seed",
            "created": today,
            "updated": today,
            "sources": ["Raw/Sources/wikimason-demo-source.md"],
            "source_count": 1,
            "aliases": ["distilled knowledge"],
        },
        body=(
            "# Compiled Knowledge\n\n"
            "A reusable note distills source material into short, linked, source-backed knowledge.\n\n"  # noqa: E501
            "## Details\n\n"
            "Example compiled note.\n\n"
            "## Related\n\n"
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Topics/wikimason'), label='WikiMason', source_path=_page_rel(config, 'Wiki/Concepts/compiled-knowledge'))}\n\n"  # noqa: E501
            "## Sources\n\n"
            f"- {format_link(config.links, 'Raw/Sources/wikimason-demo-source.md', label='wikimason demo source', source_path=_page_rel(config, 'Wiki/Concepts/compiled-knowledge'))}\n"  # noqa: E501
        ),
    )
    _write_demo_page(
        vault,
        config,
        logical_ref="Wiki/Topics/wikimason",
        metadata={
            "tags": ["topic"],
            "topics": [],
            "status": "active",
            "created": today,
            "updated": today,
            "sources": ["Raw/Sources/wikimason-demo-source.md"],
            "source_count": 1,
            "aliases": [],
        },
        body=(
            "# WikiMason\n\n"
            "Topic for WikiMason usage.\n\n"
            "## Scope\n\n"
            "Wiki workflows and maintenance.\n\n"
            "## Related\n\n"
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Concepts/compiled-knowledge'), label='Compiled Knowledge', source_path=_page_rel(config, 'Wiki/Topics/wikimason'))}\n\n"  # noqa: E501
            "## Sources\n\n"
            f"- {format_link(config.links, 'Raw/Sources/wikimason-demo-source.md', label='wikimason demo source', source_path=_page_rel(config, 'Wiki/Topics/wikimason'))}\n"  # noqa: E501
        ),
    )
    _write_demo_page(
        vault,
        config,
        logical_ref="Wiki/Projects/wikimason-demo",
        metadata={
            "tags": ["project"],
            "topics": ["Wiki/Topics/wikimason.md"],
            "status": "active",
            "created": today,
            "updated": today,
            "sources": ["Raw/Sources/wikimason-demo-source.md"],
            "source_count": 1,
            "aliases": [],
        },
        body=(
            "# WikiMason Demo\n\n"
            "Project note for demo vault.\n\n"
            "## Status\n\n"
            "Active.\n\n"
            "## Related\n\n"
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Topics/wikimason'), label='WikiMason', source_path=_page_rel(config, 'Wiki/Projects/wikimason-demo'))}\n\n"  # noqa: E501
            "## Sources\n\n"
            f"- {format_link(config.links, 'Raw/Sources/wikimason-demo-source.md', label='wikimason demo source', source_path=_page_rel(config, 'Wiki/Projects/wikimason-demo'))}\n"  # noqa: E501
        ),
    )
    _write_demo_page(
        vault,
        config,
        logical_ref="Wiki/Logs/initial-ingest",
        metadata={
            "tags": ["log"],
            "topics": ["Wiki/Topics/wikimason.md"],
            "status": "active",
            "created": today,
            "updated": today,
            "sources": ["Raw/Sources/wikimason-demo-source.md"],
            "source_count": 1,
            "aliases": [],
        },
        body=(
            "# Initial Ingest\n\n"
            "Initial ingest log.\n\n"
            "## Details\n\n"
            "- Imported demo source.\n\n"
            "## Related\n\n"
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Projects/wikimason-demo'), label='WikiMason Demo', source_path=_page_rel(config, 'Wiki/Logs/initial-ingest'))}\n\n"  # noqa: E501
            "## Sources\n\n"
            f"- {format_link(config.links, 'Raw/Sources/wikimason-demo-source.md', label='wikimason demo source', source_path=_page_rel(config, 'Wiki/Logs/initial-ingest'))}\n"  # noqa: E501
        ),
    )


def _append_gitignore(vault: Path, *, include_obsidian: bool) -> None:
    path = vault / ".gitignore"
    block = (
        BASE_GITIGNORE_BLOCK.replace(
            "# Large or private raw attachments\n",
            OBSIDIAN_GITIGNORE_BLOCK + "# Large or private raw attachments\n",
        )
        if include_obsidian
        else BASE_GITIGNORE_BLOCK
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if "# >>> wikimason >>>" in existing:
            return
        path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")
        return
    path.write_text(block, encoding="utf-8")


def _seed_missing_core_files(vault: Path, config: Any) -> None:
    for rel in _core_keep_files(config):
        _write_if_missing(vault / rel, "")
    for rel, content in CORE_EMPTY_FILES.items():
        _write_if_missing(vault / rel, content)
    _write_if_missing(
        vault / _page_rel(config, "Wiki/index"), _wiki_index_placeholder(config)
    )
    for logical_ref, content in _section_index_placeholders().items():
        _write_if_missing(vault / _page_rel(config, logical_ref), content)


def _wiki_index_placeholder(config: Any) -> str:
    top_index_rel = _page_rel(config, "Wiki/index")
    return "\n".join(
        [
            "# LLM Wiki",
            "",
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Topics/index'), label='Topics', source_path=top_index_rel)}",  # noqa: E501
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Concepts/index'), label='Concepts', source_path=top_index_rel)}",  # noqa: E501
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Entities/index'), label='Entities', source_path=top_index_rel)}",  # noqa: E501
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Projects/index'), label='Projects', source_path=top_index_rel)}",  # noqa: E501
            f"- {format_link(config.links, _page_rel(config, 'Wiki/Logs/index'), label='Logs', source_path=top_index_rel)}",  # noqa: E501
            "",
        ]
    )


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _core_keep_files(config: Any) -> list[str]:
    keep = [
        "Raw/Sources/.gitkeep",
        "Raw/Files/.gitkeep",
        "_templates/.gitkeep",
    ]
    if config.profile_config.flat_pages:
        keep.append(f"{config.profile_config.pages_dir}/.gitkeep")
    else:
        keep.extend(
            [
                "Wiki/Topics/.gitkeep",
                "Wiki/Concepts/.gitkeep",
                "Wiki/Entities/.gitkeep",
                "Wiki/Projects/.gitkeep",
                "Wiki/Logs/.gitkeep",
            ]
        )
    return keep


def _section_index_placeholders() -> dict[str, str]:
    return {
        "Wiki/Topics/index": (
            "# Topic Index\n\n"
            "Topic notes will appear here after `wikimason index build`.\n"
        ),
        "Wiki/Concepts/index": (
            "# Concept Index\n\n"
            "Concept notes will appear here after `wikimason index build`.\n"
        ),
        "Wiki/Entities/index": (
            "# Entity Index\n\n"
            "Entity notes will appear here after `wikimason index build`.\n"
        ),
        "Wiki/Projects/index": (
            "# Project Index\n\n"
            "Project notes will appear here after `wikimason index build`.\n"
        ),
        "Wiki/Logs/index": (
            "# Log Index\n\n"
            "Operational log notes will appear here after "
            "`wikimason index build`.\n"
        ),
    }


def _page_rel(config: Any, logical_ref: str) -> str:
    return logical_ref_to_relpath(logical_ref, config=config)


def _write_demo_page(
    vault: Path, config: Any, *, logical_ref: str, metadata: dict[str, Any], body: str
) -> None:
    target = vault / _page_rel(config, logical_ref)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_page_text(metadata, body, config=config), encoding="utf-8")


PURPOSE_MD = """# Wiki Purpose

Define the goals, key questions, research scope, and thesis of this wiki.

## Goals

<!-- Add wiki goals below -->

## Key Questions

<!-- Add key research questions below -->

## Scope

<!-- Define the research scope below -->
"""


L1_POLICY_MD = """# L1 Policy

L1 (always-loaded) content includes:
- Agent rules and guardrails
- Dangerous-if-missing constraints
- Broadly applicable agent behavior
- Credential and secret handling rules

L2 (on-demand) content lives in `Wiki/` and is loaded as needed:
- Project history
- Research details
- Compiled knowledge
- Workflow documentation

## Routing Rules

1. **Dangerous if missing** → L1 (Schema/)
2. **Broadly applicable agent behavior** → L1 (Schema/)
3. **Project, history, or research details** → L2 (Wiki/)
4. **Credentials or secrets** → outside tracked wiki, or gitignored L1 only

## L1 Files

- `Schema/policy.md` — agent policy and hard rules
- `Schema/l1-policy.md` — this file, defining L1/L2 routing
- `Schema/purpose.md` — wiki goals and scope
- `Schema/agent-workflow.md` — first-run and maintenance workflows
- `Schema/command-reference.md` — generated command reference
"""
