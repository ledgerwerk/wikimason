from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .config import find_local_config, load_config_data
from .constants import SOURCE_MANIFEST, SOURCE_SCHEMA_VERSION
from .errors import UsageError
from .page_profiles import default_logical_ref_for_path

if TYPE_CHECKING:
    from .config import WikiMasonConfig

DEFAULT_COMPILED_REQUIRED = (
    "type",
    "tags",
    "topics",
    "status",
    "created",
    "updated",
    "sources",
    "source_count",
    "aliases",
)
DEFAULT_SOURCE_REQUIRED = (
    "Title",
    "Author",
    "Reference",
    "ContentType",
    "Created",
    "Processed",
    "tags",
)


@dataclass(frozen=True)
class NoteKindSchema:
    name: str
    folder: str
    tag: str
    template: str
    detail_heading: str
    required_sections: tuple[str, ...]


@dataclass(frozen=True)
class StatusSchema:
    allowed: tuple[str, ...]
    incomplete_allowed: tuple[str, ...]


@dataclass(frozen=True)
class FrontmatterSchema:
    compiled_required: tuple[str, ...]
    source_required: tuple[str, ...]


@dataclass(frozen=True)
class VaultSchema:
    schema_version: int
    note_kinds: dict[str, NoteKindSchema]
    statuses: StatusSchema
    frontmatter: FrontmatterSchema
    generated: tuple[str, ...]


def default_schema() -> VaultSchema:
    note_kinds = {
        "topic": NoteKindSchema(
            name="topic",
            folder="Wiki/Topics",
            tag="topic",
            template="topic-note.md",
            detail_heading="Scope",
            required_sections=("Scope", "Related", "Sources"),
        ),
        "concept": NoteKindSchema(
            name="concept",
            folder="Wiki/Concepts",
            tag="concept",
            template="concept-note.md",
            detail_heading="Details",
            required_sections=("Details", "Related", "Sources"),
        ),
        "entity": NoteKindSchema(
            name="entity",
            folder="Wiki/Entities",
            tag="entity",
            template="entity-note.md",
            detail_heading="Details",
            required_sections=("Details", "Related", "Sources"),
        ),
        "project": NoteKindSchema(
            name="project",
            folder="Wiki/Projects",
            tag="project",
            template="project-note.md",
            detail_heading="Status",
            required_sections=("Status", "Related", "Sources"),
        ),
        "log": NoteKindSchema(
            name="log",
            folder="Wiki/Logs",
            tag="log",
            template="log-note.md",
            detail_heading="Details",
            required_sections=("Details", "Related", "Sources"),
        ),
    }
    statuses = StatusSchema(
        allowed=(
            "seed",
            "active",
            "canonical",
            "stale",
            "needs_review",
            "draft",
            "stable",
            "deprecated",
        ),
        incomplete_allowed=("draft", "seed"),
    )
    frontmatter = FrontmatterSchema(
        compiled_required=DEFAULT_COMPILED_REQUIRED,
        source_required=DEFAULT_SOURCE_REQUIRED,
    )
    generated = (
        "Wiki/catalog.jsonl",
        "Wiki/index.md",
        "Schema/frontmatter-schema.md",
        str(SOURCE_MANIFEST),
        "Schema/command-reference.md",
        "AGENTS.md",
    )
    return VaultSchema(
        schema_version=SOURCE_SCHEMA_VERSION,
        note_kinds=note_kinds,
        statuses=statuses,
        frontmatter=frontmatter,
        generated=generated,
    )


def load_vault_schema(
    vault: Path, config: WikiMasonConfig | None = None
) -> VaultSchema:
    default = default_schema()
    raw = _load_toml_schema_data(vault, config=config)
    if raw is not None:
        version = raw.get("schema_version", default.schema_version)
        if version != default.schema_version:
            raise UsageError(
                f"unsupported vault schema version: "
                f"{version} (expected {default.schema_version})"
            )
        return VaultSchema(
            schema_version=default.schema_version,
            note_kinds=_merge_note_kinds(default.note_kinds, raw.get("note_kinds", {})),
            statuses=_merge_statuses(default.statuses, raw.get("statuses", {})),
            frontmatter=_merge_frontmatter(
                default.frontmatter, raw.get("frontmatter", {})
            ),
            generated=_merge_generated(default.generated, raw.get("generated", [])),
        )
    return default


def schema_to_dict(schema: VaultSchema) -> dict[str, object]:
    return {
        "schema_version": schema.schema_version,
        "note_kinds": {
            name: {
                "folder": config.folder,
                "tag": config.tag,
                "template": config.template,
                "detail_heading": config.detail_heading,
                "required_sections": list(config.required_sections),
            }
            for name, config in schema.note_kinds.items()
        },
        "statuses": {
            "allowed": list(schema.statuses.allowed),
            "incomplete_allowed": list(schema.statuses.incomplete_allowed),
        },
        "frontmatter": {
            "compiled_required": list(schema.frontmatter.compiled_required),
            "source_required": list(schema.frontmatter.source_required),
        },
        "generated": list(schema.generated),
    }


def schema_toml_lines(schema: VaultSchema) -> list[str]:
    lines = [
        "[schema]",
        f"schema_version = {schema.schema_version}",
        "",
        "[schema.statuses]",
        f"allowed = {_toml_string_array(schema.statuses.allowed)}",
        (
            f"incomplete_allowed = "
            f"{_toml_string_array(schema.statuses.incomplete_allowed)}"
        ),
        "",
        "[schema.frontmatter]",
        (
            f"compiled_required = "
            f"{_toml_string_array(schema.frontmatter.compiled_required)}"
        ),
        f"source_required = {_toml_string_array(schema.frontmatter.source_required)}",
    ]
    for name, config in schema.note_kinds.items():
        lines.extend(
            [
                "",
                f"[schema.note_kinds.{name}]",
                f"folder = {_toml_string(config.folder)}",
                f"tag = {_toml_string(config.tag)}",
                f"template = {_toml_string(config.template)}",
                f"detail_heading = {_toml_string(config.detail_heading)}",
                f"required_sections = {_toml_string_array(config.required_sections)}",
            ]
        )
    lines.extend(
        [
            "",
            "[generated]",
            f"paths = {_toml_string_array(schema.generated)}",
        ]
    )
    return lines


def note_kind(schema: VaultSchema, kind: str) -> NoteKindSchema:
    try:
        return schema.note_kinds[kind]
    except KeyError as exc:
        raise UsageError(f"unsupported kind: {kind}") from exc


def kind_to_folder(schema: VaultSchema, kind: str) -> str:
    return note_kind(schema, kind).folder


def allowed_tags(schema: VaultSchema) -> set[str]:
    return {"source", *(config.tag for config in schema.note_kinds.values())}


def valid_statuses(schema: VaultSchema) -> set[str]:
    return set(schema.statuses.allowed)


def incomplete_allowed_statuses(schema: VaultSchema) -> set[str]:
    return set(schema.statuses.incomplete_allowed)


def compiled_prefixes(schema: VaultSchema) -> tuple[str, ...]:
    return tuple(
        f"{config.folder.rstrip('/')}/" for config in schema.note_kinds.values()
    )


def required_sections(schema: VaultSchema, kind: str) -> tuple[str, ...]:
    return note_kind(schema, kind).required_sections


def compiled_required_fields(schema: VaultSchema) -> tuple[str, ...]:
    return schema.frontmatter.compiled_required


def note_kind_for_path(schema: VaultSchema, path: str) -> str | None:
    normalized = default_logical_ref_for_path(path) or path.removesuffix(".md")
    for name, config in schema.note_kinds.items():
        if normalized.startswith(f"{config.folder.rstrip('/')}/"):
            return name
    return None


def schema_generated_paths(schema: VaultSchema) -> set[str]:
    paths = set(schema.generated)
    paths.add("Wiki/index.md")
    for config in schema.note_kinds.values():
        paths.add(f"{config.folder.rstrip('/')}/index.md")
    return paths


def render_frontmatter_schema_markdown(
    schema: VaultSchema, *, source_label: str = "wikimason.toml"
) -> str:
    lines = [
        "# Frontmatter Schema",
        "",
        f"This file is generated from `{source_label}`.",
        "",
        "## Compiled note required fields",
        "",
        *[f"- `{field}`" for field in schema.frontmatter.compiled_required],
        "",
        "## Raw source required fields",
        "",
        *[f"- `{field}`" for field in schema.frontmatter.source_required],
        "",
        "## Allowed statuses",
        "",
        *[f"- `{status}`" for status in schema.statuses.allowed],
        "",
        "## Note kinds",
        "",
    ]
    for name, config in schema.note_kinds.items():
        lines.extend(
            [
                f"### `{name}`",
                "",
                f"- Folder: `{config.folder}`",
                f"- Tag: `{config.tag}`",
                f"- Template: `{config.template}`",
                f"- Detail heading: `{config.detail_heading}`",
                "- Required sections: "
                + ", ".join(f"`{section}`" for section in config.required_sections),
                "",
            ]
        )
    lines.extend(
        [
            "## Generated files",
            "",
            *[f"- `{path}`" for path in sorted(schema_generated_paths(schema))],
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def schema_source_label(vault: Path, config: WikiMasonConfig | None = None) -> str:
    config_path = _schema_config_path(vault, config=config)
    if config_path is not None:
        return config_path.name
    return "wikimason.toml"


def _schema_config_path(
    vault: Path, config: WikiMasonConfig | None = None
) -> Path | None:
    if config is not None and config.source_path is not None:
        return config.source_path
    return find_local_config(vault)


def _load_toml_schema_data(
    vault: Path, config: WikiMasonConfig | None = None
) -> dict[str, object] | None:
    config_path = _schema_config_path(vault, config=config)
    if config_path is None:
        return None
    raw = load_config_data(config_path)
    schema_table = raw.get("schema")
    generated_table = raw.get("generated")
    if schema_table is None and generated_table is None:
        return None
    if schema_table is None:
        schema_table = {}
    if not isinstance(schema_table, dict):
        raise UsageError("invalid config: schema must be a table")
    merged = dict(schema_table)
    if generated_table is None:
        return merged
    if not isinstance(generated_table, dict):
        raise UsageError("invalid config: generated must be a table")
    merged["generated"] = generated_table.get("paths", [])
    return merged


def _merge_note_kinds(
    defaults: dict[str, NoteKindSchema], raw: object
) -> dict[str, NoteKindSchema]:
    merged = {
        name: _merge_note_kind(name, config, None) for name, config in defaults.items()
    }
    if raw is None:
        return merged
    if not isinstance(raw, dict):
        raise UsageError("invalid vault schema: note_kinds must be an object")
    for name, data in raw.items():
        if not isinstance(name, str):
            raise UsageError("invalid vault schema: note kind names must be strings")
        merged[name] = _merge_note_kind(name, defaults.get(name), data)
    return merged


def _merge_note_kind(
    name: str, default: NoteKindSchema | None, raw: object
) -> NoteKindSchema:
    if raw is not None and not isinstance(raw, dict):
        raise UsageError(f"invalid vault schema: note kind {name} must be an object")
    row = raw if isinstance(raw, dict) else {}
    detail_heading = _string_value(
        row.get("detail_heading"),
        default.detail_heading if default else "Details",
        label=f"note kind {name} detail_heading",
    )
    required_default = (
        default.required_sections if default else (detail_heading, "Related", "Sources")
    )
    required = _string_tuple(
        row.get("required_sections"),
        required_default,
        label=f"note kind {name} required_sections",
    )
    return NoteKindSchema(
        name=name,
        folder=_string_value(
            row.get("folder"),
            default.folder if default else f"Wiki/{name.replace('-', ' ').title()}",
            label=f"note kind {name} folder",
        ),
        tag=_string_value(
            row.get("tag"),
            default.tag if default else name,
            label=f"note kind {name} tag",
        ),
        template=_string_value(
            row.get("template"),
            default.template if default else f"{name}-note.md",
            label=f"note kind {name} template",
        ),
        detail_heading=detail_heading,
        required_sections=required,
    )


def _merge_statuses(default: StatusSchema, raw: object) -> StatusSchema:
    if raw is None:
        return default
    if not isinstance(raw, dict):
        raise UsageError("invalid vault schema: statuses must be an object")
    return StatusSchema(
        allowed=_string_tuple(
            raw.get("allowed"), default.allowed, label="statuses.allowed"
        ),
        incomplete_allowed=_string_tuple(
            raw.get("incomplete_allowed"),
            default.incomplete_allowed,
            label="statuses.incomplete_allowed",
        ),
    )


def _merge_frontmatter(default: FrontmatterSchema, raw: object) -> FrontmatterSchema:
    if raw is None:
        return default
    if not isinstance(raw, dict):
        raise UsageError("invalid vault schema: frontmatter must be an object")
    return FrontmatterSchema(
        compiled_required=_string_tuple(
            raw.get("compiled_required"),
            default.compiled_required,
            label="frontmatter.compiled_required",
        ),
        source_required=_string_tuple(
            raw.get("source_required"),
            default.source_required,
            label="frontmatter.source_required",
        ),
    )


def _merge_generated(defaults: tuple[str, ...], raw: object) -> tuple[str, ...]:
    return _string_tuple(raw, defaults, label="generated")


def _string_value(value: object, default: str, *, label: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise UsageError(f"invalid vault schema: {label} must be a string")
    return value.strip() or default


def _string_tuple(
    value: object, default: tuple[str, ...], *, label: str
) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list):
        raise UsageError(f"invalid vault schema: {label} must be a list")
    rows: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise UsageError(f"invalid vault schema: {label} entries must be strings")
        stripped = item.strip()
        if stripped:
            rows.append(stripped)
    return tuple(rows) or default


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_string_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"
