---
title: "Architecture Documentation"
date: "1980-01-01"
generator: "archledger 0.1.1.dev11+gbbef02d12"
arc42_template_version: "9.0-EN"
---

# Architecture Documentation

Generated from archledger records. Do not edit this generated file directly.

# Introduction and Goals

WikiMason is a filesystem-backed CLI toolkit for building and maintaining an LLM wiki. It supports Obsidian, Markdown, and generic tool profiles through a profile abstraction layer.

The project serves two primary stakeholder groups: coding agents that consume compiled `AGENTS.md` context, and human maintainers who manage the wiki through CLI commands. It emphasizes deterministic local-first operations with no network dependencies.

Key quality goals include deterministic filesystem operations, source traceability through manifest tracking, and lint coverage for all compiled notes.

## Requirements Overview

| Title                                                  | Priority | Source | Stakeholders | Quality goals |
| ------------------------------------------------------ | -------- | ------ | ------------ | ------------- |
| Filesystem-backed CLI toolkit for LLM wiki maintenance | must     |        |              |               |

## Quality Goals

| Title                                | Priority | Scenario                                                                                                                     |
| ------------------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Deterministic local-first operations | 1        | All CLI commands produce identical filesystem state when run with the same inputs, regardless of environment or prior state. |

## Stakeholders

| Title                             | Contact | Expectations                                                                                                                                  |
| --------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Coding agents consuming AGENTS.md |         | AGENTS.md is always current and reflects actual vault state, Command reference is complete and accurate, Policy rules are enforced by tooling |
| Human wiki maintainers            |         | CLI commands are predictable and well-documented, Lint catches errors before they reach agents, Vault operations are safe and reversible      |

# Architecture Constraints

WikiMason operates under several architectural constraints that shape its design:

- **Single flat package**: All source code lives in `wikimason/` at the repository root; no `src/` layout.
- **Python 3.10+**: Minimum Python version with `tomllib` fallback via `tomli` for older versions.
- **Minimal dependencies**: Runtime dependencies limited to Typer, Click, PyYAML, rapidfuzz, fuzzysearch, and tomli.
- **Deterministic filesystem operations**: No network calls, no database, no daemon processes.
- **No upstream obsidian-cli**: All wiki operations use only the WikiMason CLI.
- **Single project skill**: One skill file at `skills/wikimason/SKILL.md` defines agent behavior.

- **Python 3.10+ with minimal dependencies**
  - Impact: high
  - Notes: ## Constraint

WikiMason must support Python 3.10 and later with a minimal set of runtime dependencies (typer, click, PyYAML, rapidfuzz, fuzzysearch, tomli).

## Rationale

- Python 3.10+ provides `tomllib` in stdlib; `tomli` fallback for older versions.
- Minimal dependencies reduce installation friction and supply-chain risk.
- No compiled extensions required; pure Python distribution.
- **Single package at repository root**
  - Impact: high
  - Notes: ## Constraint

The entire WikiMason codebase lives in a single `wikimason/` package directory at the repository root. No `src/` layout is used.

## Rationale

- Simplifies imports and installation via `pyproject.toml` `[tool.setuptools.packages.find]`.
- Consistent with the project's goal of minimal structural overhead.
- Referenced in README key design constraint #1.
- **No upstream obsidian-cli dependency**
  - Impact: medium
  - Notes: ## Constraint

WikiMason must not invoke upstream `obsidian` or `obsidian-cli`. All wiki operations use only the WikiMason CLI.

## Rationale

- WikiMason is a standalone toolkit that provides its own filesystem-backed operations.
- Upstream Obsidian CLI is not required and would introduce external runtime dependencies.
- Stated as a hard rule in `skills/wikimason/SKILL.md`.
- **Deterministic filesystem operations only**
  - Impact: high
  - Notes: ## Constraint

All WikiMason operations are deterministic filesystem reads and writes. No network calls, no database, no daemon processes.

## Rationale

- Ensures reproducibility and debuggability.
- Works offline, consistent with local-first wiki management.
- Referenced in README key design constraint #3.

# Context and Scope

WikiMason interacts with several external systems and interfaces:

- **CLI users**: Human operators interact exclusively through the Typer/Click command-line interface. All commands support `--format json` for machine-readable output.
- **Obsidian vault filesystem**: When configured with the `obsidian` profile, WikiMason reads and writes Obsidian-compatible vaults with `.obsidian/` directory and wikilink syntax.
- **Markdown files with YAML frontmatter**: Primary content format for all pages, sources, and templates.
- **Git repository**: Vaults are designed for Git version control with auto-generated `.gitignore` and pre-commit hooks.
- **pip/PyPI**: Distribution channel for the Python package.

Internal scope is bounded by the vault root directory; WikiMason never operates outside its configured vault.

## Business Context

<!-- archledger: no accepted records for this section yet -->

## Technical Context

- **Markdown files with YAML frontmatter** -> Markdown editor / Obsidian
  - Describe this context interface.
- **Obsidian vault filesystem** -> Obsidian
  - ## Context Interface

WikiMason reads and writes Obsidian-compatible vaults on the local filesystem. The `obsidian` profile configures `.obsidian/` dot-directory creation and Obsidian-URI opening.

## Details

- Obsidian vaults use YAML frontmatter and `[[wikilink]]` syntax.
- `.obsidian/` directory created when `create_dot_dir = true`.
- `open_uri_template = "obsidian://open?path={path}"` for deep linking.
- Excludes `.obsidian/workspace*.json`, `.obsidian/cache/`, `.obsidian/plugins/` from processing.
- **Git repository for version control** -> Git
  - ## Context Interface

WikiMason vaults are designed to be version-controlled with Git. The `init` command generates `.gitignore` entries and pre-commit hooks.

## Details

- Auto-generated `.gitignore` blocks exclude `Raw/Files/*`, Python artifacts, and Obsidian local state.
- Pre-commit hook at `.githooks/pre-commit` runs `wikimason vault maintain`.
- `AGENTS.md` is compiled and tracked in the repository.

# Solution Strategy

WikiMason employs three core solution strategies:

1. **Profile-based configuration**: A profile system (`markdown`, `obsidian`, `logseq`) adapts identical core logic to different tool layouts. Configuration cascades from built-in defaults through local `wikimason.toml` files to named env configs.

2. **Source lifecycle management**: Raw sources in `Raw/Sources/` are tracked through a lifecycle pipeline: scan (index), delta (detect changes), verify (validate), lint (check). The source manifest (`Schema/source-manifest.jsonl`) and sidecar metadata files provide traceability.

3. **Ingest workflow**: The ingest pipeline (`ingest.py`) orchestrates source scanning, note creation, linting, catalog building, and validation into a single workflow with clear exit codes and machine-readable JSON output.

## Strategy Items

## Profile-based configuration adapts to multiple tool layouts

**Drivers:**
**Constraints:**
**Related ADRs:**

## Strategy

WikiMason uses a profile system to adapt identical core logic to different tool layouts (Markdown, Obsidian, Logseq).

## Details

- Three built-in profiles: `markdown`, `obsidian`, `logseq`.
- Each profile defines paths, link format, and profile-specific settings.
- `profiles.py` holds `_PROFILES` dict with `WikiProfileDefaults` dataclass instances.
- `profile_defaults()` merges profile config with `DEFAULT_PATHS`.
- Configuration is loaded from `wikimason.toml` or `.wikimason.toml` files.

## Source lifecycle management: scan, delta, verify, lint

**Drivers:**
**Constraints:**
**Related ADRs:**

## Strategy

Raw source files in `Raw/Sources/` are tracked through a lifecycle: scan (index), delta (detect changes), verify (validate), and lint (check).

## Details

- Module split across `source_scan.py`, `source_delta.py`, `source_verify.py`, `source_manifest.py`, `source_metadata.py`.
- Manifest stored as `Schema/source-manifest.jsonl`.
- Sidecar files (`*.wm.yaml`) hold computed metadata per source.
- Coverage tracking identifies sources with and without compiled notes.

## Ingest workflow bridges raw sources to compiled notes

**Drivers:**
**Constraints:**
**Related ADRs:**

## Strategy

The ingest workflow (`ingest.py`) orchestrates source scanning, note creation, linting, and catalog building in a single pipeline.

## Details

- `ingest status`: Reports vault health (doctor, lint, source coverage).
- `ingest plan`: Generates recommended note creation commands per actionable source.
- `ingest finish`: Runs build + source scan + lint + doctor, returns unified result.
- Exit code 0 = clean, 1 = errors, 2 = actionable work remaining.

# Building Block View

WikiMason is organized into seven layered subsystems, all within the `wikimason/` package:

- **CLI Layer**: Typer command groups and entrypoint routing (`cli.py`, `cli_app.py`, `cli_groups/`).
- **Config Layer**: TOML config loading, profile defaults, path resolution (`config.py`, `profiles.py`).
- **Filesystem Operations**: File CRUD, path resolution, note scaffolding (`files.py`, `paths.py`, `notes.py`).
- **Source Lifecycle**: Source scanning, delta detection, manifest management (`sources.py`, `source_scan.py`, `source_delta.py`, `source_verify.py`, `source_manifest.py`, `source_metadata.py`).
- **Build Pipeline**: Vault build, index generation, catalog writing, AGENTS.md compilation (`build.py`, `catalog.py`, `agents.py`).
- **Lint and Validation**: Frontmatter validation, link checking, credential scanning (`lint.py`, `lint_rules.py`, `lint_links.py`, `lint_credentials.py`).
- **Search and Indexing**: Fuzzy search, candidate ranking, search backends (`search.py`, `search_backends.py`, `search_index.py`).

Supporting modules include `schema.py` (frontmatter schema), `templates.py` (Jinja2-like templates), `scaffold.py` (vault initialization), and `commands.py` (command reference generation).

## Whitebox WikiMason System

## White Box: WikiMason System

The WikiMason CLI toolkit is a Python application composed of six layered subsystems.

### Contained Black Boxes

1. **CLI Layer** — Typer command groups and entrypoint routing.
2. **Config Layer** — TOML config loading, profile defaults, path resolution.
3. **Filesystem Operations** — File CRUD, path resolution, note scaffolding.
4. **Source Lifecycle** — Source scanning, delta detection, manifest management.
5. **Build Pipeline** — Vault build, index generation, catalog writing, AGENTS.md compilation.
6. **Lint & Validation** — Frontmatter validation, link checking, credential scanning.
7. **Search & Indexing** — Fuzzy search, candidate ranking, search backends.

# Runtime View

Three primary runtime scenarios define WikiMason's operational behavior:

1. **Vault initialization** (`wikimason init`): Creates directory structure, writes config and templates, compiles AGENTS.md, sets up gitignore and pre-commit hooks. Optionally seeds demo content.

2. **Source ingest workflow**: Discovers raw sources via `source scan`, detects changes via `source delta`, generates note creation plans via `ingest plan`, creates compiled notes via `note new`, and validates the result via `ingest finish`.

3. **Vault build and maintenance** (`wikimason vault maintain` / `wikimason vault build`): Syncs source counts, writes catalog JSONL, rebuilds index pages, updates schema documentation, and compiles AGENTS.md with embedded input hashes for change detection.

All workflows produce JSON output when `--format json` is specified and use exit codes 0 (clean), 1 (errors), and 2 (actionable work remaining).

## Vault initialization workflow

## Runtime Scenario: Vault Initialization

### Sequence

1. User runs `wikimason init [profile] [path]`.
2. CLI resolves profile via `canonical_profile_name()`.
3. `init_vault()` in `scaffold.py` creates directory structure:
   - Core directories: `Raw/Sources/`, `Raw/Files/`, `Wiki/`, `Schema/`, `_templates/`.
   - Per-kind subdirectories under `Wiki/`: `Topics/`, `Concepts/`, `Entities/`, `Projects/`, `Logs/`.
   - `.gitkeep` files in empty directories.
4. Config file `wikimason.toml` written with profile defaults.
5. Template files written to `_templates/`: source-note, topic-note, concept-note, entity-note, project-note, log-note.
6. Schema documentation written: `frontmatter-schema.md`, `command-reference.md`, `agent-workflow.md`, `policy.md`, `purpose.md`, `l1-policy.md`.
7. `AGENTS.md` compiled from schema and templates.
8. `.gitignore` appended with WikiMason block.
9. Pre-commit hook created at `.githooks/pre-commit`.
10. If `--demo` flag: demo source and compiled notes created, vault built, sources scanned.

## Source ingest workflow

## Runtime Scenario: Source Ingest

### Sequence

1. User adds markdown files to `Raw/Sources/`.
2. `wikimason source scan --update`:
   - `source_scan.py` discovers all `*.md` files in `Raw/Sources/`.
   - Extracts frontmatter, computes SHA-256 hash, determines source kind.
   - Builds source records and writes `Schema/source-manifest.jsonl`.
   - Creates/updates sidecar `*.wm.yaml` files.
3. `wikimason source delta`:
   - Compares current filesystem state against manifest.
   - Reports new, changed, metadata-changed, and missing-coverage sources.
4. `wikimason ingest plan`:
   - Generates `wikimason note new` commands for each actionable source.
   - Recommends topic, concept, and log notes per source.
5. `wikimason note new --kind topic --title "..." --source "..." --allow-incomplete`:
   - Creates compiled note in `Wiki/Topics/` with frontmatter and template body.
   - Links back to the raw source file.
6. User edits note body, adds related links.
7. `wikimason ingest finish --accept-covered`:
   - Rebuilds vault (`build_vault`).
   - Re-scans sources, accepts covered sources.
   - Runs lint and source lint.
   - Reports unified status.

## Vault build and maintenance workflow

## Runtime Scenario: Vault Build and Maintenance

### Sequence

1. `wikimason vault build` (or `wikimason vault maintain`):
   - `build_vault()` orchestrates the following steps.
2. `sync_source_count()`:
   - Iterates all compiled markdown files.
   - Updates `source_count` frontmatter field to match actual `sources` list length.
3. `iter_catalog_entries()` + `write_catalog()`:
   - Scans all compiled notes, extracts title, kind, tags, status, summary, sources.
   - Writes `Wiki/catalog.jsonl`.
4. `rebuild_indexes()`:
   - Generates `Wiki/index.md` with links to per-kind section indexes.
   - Generates `Wiki/Topics/index.md`, `Wiki/Concepts/index.md`, etc.
5. Schema documentation updated:
   - `Schema/frontmatter-schema.md`: Rendered from `VaultSchema` dataclass.
   - `Schema/command-reference.md`: Rendered from `COMMAND_SPECS`.
6. `write_agents_md()`:
   - Compiles `AGENTS.md` from schema, templates, policy, command reference.
   - Preserves manual blocks between `WIKIMASON:MANUAL BEGIN/END` markers.
   - Embeds input hashes in HTML comment for change detection.

# Deployment View

WikiMason deploys as a standard Python package with two deployment contexts:

1. **pip-installable package**: Distributed via `pyproject.toml` with setuptools build backend. Entrypoint `wikimason = "wikimason.cli:main"`. Runtime dependencies: typer, click, PyYAML, rapidfuzz, fuzzysearch, tomli.

2. **Local filesystem vault**: Each wiki vault is a directory tree on the local filesystem, typically version-controlled with Git. Vault root is auto-detected by presence of `wikimason.toml`, `.obsidian/`, core vault directories, or `AGENTS.md`.

The package is installed via `python -m pip install -e '.[dev]'` for development or directly from PyPI. Vaults require no additional deployment steps beyond `wikimason init`.

## pip-installable Python package

## Infrastructure: Python Package

WikiMason is distributed as a standard Python package installable via pip.

### Details

- `pyproject.toml` defines build system (setuptools), dependencies, and entrypoint.
- Entrypoint: `wikimason = "wikimason.cli:main"`.
- Dependencies: typer, click, PyYAML, rapidfuzz, fuzzysearch, tomli (for Python < 3.11).
- Optional `[dev]` extras: mypy, pytest, ruff, build, twine.
- Optional `[rich]` extra: rich for enhanced terminal output.

## Local filesystem vault

## Infrastructure: Local Filesystem Vault

The wiki vault is a directory tree on the local filesystem, optionally version-controlled with Git.

### Details

- Vault root detected by presence of `wikimason.toml`, `.obsidian/`, core vault dirs, or `AGENTS.md`.
- Vault structure determined by active profile config.
- All operations read/write files directly, no server or database.
- Compatible with Obsidian: vault can be opened simultaneously in Obsidian and managed with WikiMason.

# Cross-cutting Concepts

Three cross-cutting concepts permeate the WikiMason codebase:

1. **Profile system**: The `profiles.py` module defines three built-in profiles (`markdown`, `obsidian`, `logseq`) as `WikiProfileDefaults` dataclasses. Each profile specifies paths, link format, frontmatter style, page layout, and excluded patterns. All downstream modules consume config via `load_runtime_config()` without conditional branching on profile name.

2. **Frontmatter and page profiles**: A dual-layer metadata system separates raw YAML parsing (`frontmatter.py`) from profile-aware rendering (`page_profiles.py`). The latter handles format differences like Logseq's `property::` syntax versus YAML frontmatter.

3. **Link format system**: `link_format.py` provides configurable link rendering via `LinkConfig` (style, template, target, label). Used consistently across notes, catalogs, indexes, and AGENTS.md for uniform link generation.

## Profile system

## Concept: Profile System

WikiMason adapts to multiple tool layouts through a profile abstraction.

### Profiles

| Profile    | Frontmatter  | Page Layout  | Dot-Dir      | URI Scheme    |
| ---------- | ------------ | ------------ | ------------ | ------------- |
| `markdown` | YAML         | Nested Wiki/ | No           | None          |
| `obsidian` | YAML         | Nested Wiki/ | `.obsidian/` | `obsidian://` |
| `logseq`   | `property::` | Flat pages/  | No           | None          |

### Implementation

- `profiles.py`: `_PROFILES` dict maps profile names to `WikiProfileDefaults`.
- `canonical_profile_name()`: Normalize and validate profile names, supports aliases.
- `profile_defaults()`: Return merged profile config for use in `default_config()`.

### Impact

All downstream modules (`files.py`, `notes.py`, `build.py`, `page_profiles.py`) consume config via `load_runtime_config()` and behave differently based on the active profile without conditional branches on profile name.

## Frontmatter and page profiles

## Concept: Frontmatter and Page Profiles

WikiMason abstracts page metadata handling behind a dual-layer system: `frontmatter.py` for raw YAML parsing and `page_profiles.py` for profile-aware rendering.

### Layers

1. **`frontmatter.py`**: Generic YAML frontmatter split/merge/render. Used for simple files (templates, source notes).
2. **`page_profiles.py`**: Profile-aware layer that handles:
   - Logical ref to relative path conversion (`logical_ref_to_relpath`).
   - Page text splitting that respects flat vs. nested directory layouts.
   - Logseq-style `property:: value` syntax when `property_style = "logseq"`.
   - Frontmatter field ordering and formatting per profile.

### Key Functions

- `split_page_text(text, config)`: Split a page into metadata dict and body, handling profile-specific formats.
- `render_page_text(data, body, config)`: Render a page with profile-appropriate metadata formatting.
- `update_page_text(text, updates, config)`: Update specific frontmatter fields in-place.

## Link format system

## Concept: Link Format System

WikiMason supports configurable link rendering via `link_format.py`.

### Configuration

- `links.style`: `"wikilink"` produces `[[target|label]]`.
- `links.template`: Format string, e.g., `"[[{target}|{label}]]"`.
- `links.target`: Target format (`"path_no_ext"`, `"path"`, etc.).
- `links.label`: Label format (`"title_or_stem"`, `"title"`, `"stem"`).

### Key Functions

- `format_link(config, path, label, source_path)`: Render a link in the configured style.
- `extract_internal_links(text)`: Parse wikilinks from markdown text.
- `normalize_internal_link_target(target)`: Strip wikilink brackets and resolve extensions.
- `link_candidate_keys(path)`: Generate search keys for a path (with/without extension, stem only).

### Cross-cutting Impact

Used by `notes.py` for source/related links, `build.py` for index generation, `catalog.py` for catalog links, and `agents.py` for AGENTS.md rendering.

# Architecture Decisions

Three key architecture decisions shape WikiMason:

1. **Typer/Click for CLI**: Chosen for type-annotated parameter parsing, nested command groups, and JSON output support. Custom `FuzzyCommandGroup` extends Typer with fuzzy command suggestions.

2. **YAML frontmatter for metadata**: Selected for broad compatibility with Obsidian, Jekyll, Hugo, and static site generators. `frontmatter.py` handles parsing, `page_profiles.py` adapts per tool profile.

3. **JSONL for catalog and manifest**: Chosen for append-friendly streaming writes. Both `Wiki/catalog.jsonl` and `Schema/source-manifest.jsonl` use one-JSON-object-per-line format for incremental updates without full-file rewrites.

## Use Typer/Click for CLI framework

**Status:** proposed
**Date:** 2026-05-30
**Deciders:** WikiMason Contributors
**Supersedes:**
**Related:**

## Decision

Use Typer (built on Click) as the CLI framework for WikiMason.

## Context

WikiMason needed a CLI framework that supports nested command groups, global options, JSON output, and type-annotated parameter parsing.

## Consequences

- Typer provides automatic help text generation from function signatures and docstrings.
- Click integration enables `standalone_mode=False` for controlled exit handling.
- Custom `FuzzyCommandGroup` extends Typer with fuzzy command suggestions.
- Dependencies: `typer` and `click` in `pyproject.toml`.

## Use YAML frontmatter for page metadata

**Status:** proposed
**Date:** 2026-05-30
**Deciders:** WikiMason Contributors
**Supersedes:**
**Related:**

## Decision

Store page metadata as YAML frontmatter blocks (`---` delimited) at the top of Markdown files.

## Context

Wiki pages need structured metadata (tags, status, sources, aliases) that is both human-readable and machine-parseable.

## Consequences

- Compatible with Obsidian, Jekyll, Hugo, and most static site generators.
- `frontmatter.py` handles parsing/serialization via PyYAML.
- `page_profiles.py` adapts frontmatter handling per tool profile (e.g., Logseq uses `property::` syntax instead).
- Required fields defined in schema (`DEFAULT_COMPILED_REQUIRED`).

## Use JSONL for catalog and source manifest

**Status:** proposed
**Date:** 2026-05-30
**Deciders:** WikiMason Contributors
**Supersedes:**
**Related:**

## Decision

Store the note catalog as `Wiki/catalog.jsonl` and the source manifest as `Schema/source-manifest.jsonl`, both in JSON Lines format.

## Context

Both the catalog and source manifest are append-friendly, line-oriented datasets that benefit from streaming read/write.

## Consequences

- JSONL is trivially appendable without rewriting the entire file.
- Each line is a standalone JSON object, supporting incremental updates.
- Easily consumable by both Python and shell tools (`jq`, `grep`).
- `catalog.py` iterates entries and writes `catalog.jsonl`; `source_manifest.py` handles manifest persistence.

# Quality Requirements

WikiMason targets two primary quality requirements:

1. **Lint coverage for all compiled notes**: Every compiled wiki note must pass lint validation without errors. Required frontmatter fields, resolved wikilinks, and credential-free content are enforced by `lint.py` and its sub-modules.

2. **Source traceability via source_count parity**: Every compiled note must maintain accurate `source_count` matching its `sources` list. `sync_source_count()` in `build.py` detects and fixes mismatches. `source_coverage_report()` provides bidirectional source-to-note mapping.

## Quality Requirements Overview

| Title                                       | Category | Measure | Scenarios |
| ------------------------------------------- | -------- | ------- | --------- |
| Lint coverage for all compiled notes        |          |         |           |
| Source traceability via source_count parity |          |         |           |

## Quality Scenarios

<!-- archledger: no accepted records for this section yet -->

# Risks and Technical Debt

Two notable risks and technical debt items:

1. **Growing CLI surface area**: With 20+ command groups and many subcommands, the CLI surface risks becoming difficult to document, test, and maintain. Mitigated by centralized `COMMAND_SPECS` in `command_specs.py` and auto-generated command reference documentation.

2. **Frontmatter schema drift across profiles**: Three profiles with different metadata formats (YAML frontmatter vs. Logseq `property::` syntax) risk schema drift. Mitigated by centralized `VaultSchema` definition and profile-aware validation in `lint_rules.py`.

## Risk Overview

| Title                                    | Severity | Probability | Mitigation                                                                              | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------- | -------- | ----------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Growing CLI surface area                 | medium   | high        | Centralized COMMAND_SPECS, auto-generated command reference, fuzzy command suggestions. | ## Risk: Growing CLI Surface Area ### Description WikiMason currently exposes 20+ command groups with many subcommands. As features are added, the CLI surface may become difficult to document, test, and maintain. ### Impact - User confusion from command overload. - Test coverage burden grows linearly with commands. - Documentation drift between `COMMAND_SPECS`, skill file, and actual implementation. ### Mitigation - `command_specs.py` centralizes all command metadata in `COMMAND_SPECS` list. - `commands.py` generates command reference documentation from specs. - `wikimason agents compile` regenerates AGENTS.md with canonical command reference. - Fuzzy command suggestions help users discover commands. |
| Frontmatter schema drift across profiles | low      | medium      | Centralized VaultSchema, profile-aware validation in lint_rules.py, shared test suite.  | ## Risk: Frontmatter Schema Drift Across Profiles ### Description Three profiles (markdown, obsidian, logseq) use different metadata formats. Adding a new required field or changing field semantics may not be consistently applied across all profiles. ### Impact - Logseq's `property::` syntax differs fundamentally from YAML frontmatter. - Schema validation rules may not cover Logseq-style pages equally. - Template files may drift from schema definitions. ### Mitigation - `VaultSchema` dataclass defines required fields centrally. - `page_profiles.py` abstracts profile-specific rendering. - `lint_rules.py` applies profile-aware validation.                                                                  |

# Glossary

Key terms in the WikiMason domain:

- **Vault**: Root directory of a WikiMason wiki containing `Raw/`, `Wiki/`, `Schema/`, `_templates/`.
- **Source**: A raw markdown file in `Raw/Sources/` serving as input material for compiled notes. Untrusted content, never instructions.
- **Compiled Note**: A markdown file in `Wiki/` with YAML frontmatter that distills sources into structured knowledge.
- **Ingest**: The pipeline transforming raw sources into compiled notes via scanning, note creation, linting, and validation.
- **Profile**: A named configuration preset (`markdown`, `obsidian`, `logseq`) tailoring behavior to a specific tool layout.
- **Catalog**: A JSONL file (`Wiki/catalog.jsonl`) with extracted metadata for all compiled notes.
- **AGENTS.md**: Compiled markdown at vault root serving as primary context for coding agents.

| Term          | Definition |
| ------------- | ---------- |
| Vault         | See body.  |
| Source        | See body.  |
| Compiled Note | See body.  |
| Ingest        | See body.  |
| Profile       | See body.  |
| Catalog       | See body.  |
| AGENTS.md     | See body.  |
