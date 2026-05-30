"""Canonical command specifications for WikiMason.

This is the single source of truth for all command metadata. Both
:mod:`wikimason.commands` (help/docs rendering) and
:mod:`wikimason.command_registry` (search/suggestions) consume this
module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    """Machine-readable description of one CLI command."""

    path: tuple[str, ...]
    usage: str
    summary: str
    aliases: tuple[tuple[str, ...], ...] = ()
    json_output: bool = False
    agent_safe: bool = True
    hidden: bool = False


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    # -- init --
    CommandSpec(
        path=("init",),
        usage="wikimason init [markdown|obsidian|logseq] [PATH]"
        " [--profile PROFILE] [--demo] [--env NAME] [--format text|json]",
        summary="Initialize a new wiki vault.",
        json_output=True,
    ),
    CommandSpec(
        path=("config",),
        usage="wikimason config [COMMAND] [--help]",
        summary="Configuration commands.",
    ),
    # -- config --
    CommandSpec(
        path=("config", "show"),
        usage="wikimason config show [--format text|json]",
        summary="Show the active config.",
        json_output=True,
    ),
    CommandSpec(
        path=("config", "edit"),
        usage="wikimason config edit",
        summary="Open the active WikiMason config file in $EDITOR.",
    ),
    CommandSpec(
        path=("config", "validate"),
        usage="wikimason config validate [--format text|json]",
        summary="Validate the active config.",
        json_output=True,
    ),
    # -- source --
    CommandSpec(
        path=("source",),
        usage="wikimason source [COMMAND] [--help]",
        summary="Raw source management commands.",
    ),
    CommandSpec(
        path=("source", "add"),
        usage="wikimason source add PATH [--move] [--format text|json]",
        summary="Add a raw source file.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "list"),
        usage="wikimason source list [--format text|json]",
        summary="List raw source files.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "show"),
        usage="wikimason source show PATH [--vault PATH] [--format text|json]",
        summary="Show one raw source plus its current manifest record.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "verify"),
        usage="wikimason source verify [--strict] [--vault PATH] [--format text|json]",
        summary="Verify raw-source state against the current"
        " manifest and coverage delta.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "rehash"),
        usage="wikimason source rehash [--vault PATH]"
        " [--accept-covered] [--format text|json]",
        summary="Rewrite manifest hashes from the current raw-source files.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "resolve"),
        usage="wikimason source resolve QUERY [--format text|json]",
        summary="Resolve a source path by fuzzy query.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "read"),
        usage="wikimason source read QUERY [--lines N] [--first] [--format text|json]",
        summary="Read a source file by path or fuzzy query.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "scan"),
        usage="wikimason source scan [--update]"
        " [--accept-covered] [--details] [--format text|json]",
        summary="Scan raw sources and update manifest.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "delta"),
        usage="wikimason source delta [--check] [--details] [--format text|json]",
        summary="Show delta between manifest and files.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "coverage"),
        usage="wikimason source coverage [PATH] [--details] [--format text|json]",
        summary="Show source coverage report.",
        json_output=True,
    ),
    CommandSpec(
        path=("source", "lint"),
        usage="wikimason source lint [--format text|json]",
        summary="Lint source manifest.",
        json_output=True,
    ),
    # -- file --
    CommandSpec(
        path=("file",),
        usage="wikimason file [COMMAND] [--help]",
        summary="File operations.",
    ),
    CommandSpec(
        path=("file", "list"),
        usage="wikimason file list [PATH] [--total] [--format text|json]",
        summary="List files in the vault.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "read"),
        usage="wikimason file read PATH [--format text|json]",
        summary="Read a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "write"),
        usage="wikimason file write PATH --content TEXT"
        " [--overwrite] [--template NAME] [--title TITLE]"
        " [--format text|json]",
        summary="Write a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "append"),
        usage="wikimason file append PATH --content TEXT"
        " [--inline] [--format text|json]",
        summary="Append to a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "prepend"),
        usage="wikimason file prepend PATH --content TEXT [--format text|json]",
        summary="Prepend to a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "move"),
        usage="wikimason file move OLD NEW [--format text|json]",
        summary="Move a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "rename"),
        usage="wikimason file rename OLD NEW [--format text|json]",
        summary="Rename a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "delete"),
        usage="wikimason file delete PATH [--permanent] [--format text|json]",
        summary="Delete a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "open"),
        usage="wikimason file open PATH [--format text|json]",
        summary="Open a file.",
        json_output=True,
    ),
    CommandSpec(
        path=("file", "search"),
        usage="wikimason file search --query QUERY"
        " [--path PATH] [--limit N] [--context]"
        " [--case] [--fuzzy] [--total] [--format text|json]",
        summary="Search files for text.",
        json_output=True,
    ),
    # -- folder --
    CommandSpec(
        path=("folder",),
        usage="wikimason folder [COMMAND] [--help]",
        summary="Folder operations.",
    ),
    CommandSpec(
        path=("folder", "list"),
        usage="wikimason folder list [PATH] [--total] [--format text|json]",
        summary="List folders.",
        json_output=True,
    ),
    CommandSpec(
        path=("folder", "info"),
        usage="wikimason folder info [PATH] [--files] [--format text|json]",
        summary="Folder info.",
        json_output=True,
    ),
    # -- daily --
    CommandSpec(
        path=("daily",),
        usage="wikimason daily [COMMAND] [--help]",
        summary="Daily note operations.",
    ),
    CommandSpec(
        path=("daily", "path"),
        usage="wikimason daily path [DATE] [--format text|json]",
        summary="Show daily note path.",
        json_output=True,
    ),
    CommandSpec(
        path=("daily", "read"),
        usage="wikimason daily read [DATE] [--format text|json]",
        summary="Read daily note.",
        json_output=True,
    ),
    CommandSpec(
        path=("daily", "append"),
        usage="wikimason daily append --content TEXT [DATE] [--format text|json]",
        summary="Append to daily note.",
        json_output=True,
    ),
    CommandSpec(
        path=("daily", "prepend"),
        usage="wikimason daily prepend --content TEXT [DATE] [--format text|json]",
        summary="Prepend to daily note.",
        json_output=True,
    ),
    # -- property --
    CommandSpec(
        path=("property",),
        usage="wikimason property [COMMAND] [--help]",
        summary="Frontmatter property operations.",
    ),
    CommandSpec(
        path=("property", "list"),
        usage="wikimason property list [PATH] [--total] [--format text|json]",
        summary="List property names.",
        json_output=True,
    ),
    CommandSpec(
        path=("property", "get"),
        usage="wikimason property get PATH KEY [--format text|json]",
        summary="Get a property value.",
        json_output=True,
    ),
    CommandSpec(
        path=("property", "set"),
        usage="wikimason property set PATH KEY VALUE"
        " [--type TYPE] [--format text|json]",
        summary="Set a property value.",
        json_output=True,
    ),
    CommandSpec(
        path=("property", "remove"),
        usage="wikimason property remove PATH KEY [--format text|json]",
        summary="Remove a property.",
        json_output=True,
    ),
    CommandSpec(
        path=("property", "aliases"),
        usage="wikimason property aliases PATH"
        " [--add ALIAS ...] [--remove ALIAS ...]"
        " [--format text|json]",
        summary="Update aliases.",
        json_output=True,
    ),
    # -- tag --
    CommandSpec(
        path=("tag",),
        usage="wikimason tag [COMMAND] [--help]",
        summary="Tag operations.",
    ),
    CommandSpec(
        path=("tag", "list"),
        usage="wikimason tag list [--counts] [--sort-count] [--total] [--format text|json]",  # noqa: E501
        summary="List tags.",
        json_output=True,
    ),
    CommandSpec(
        path=("tag", "count"),
        usage="wikimason tag count NAME [--format text|json]",
        summary="Count tag occurrences.",
        json_output=True,
    ),
    # -- task --
    CommandSpec(
        path=("task",),
        usage="wikimason task [COMMAND] [--help]",
        summary="Task list operations.",
    ),
    CommandSpec(
        path=("task", "list"),
        usage="wikimason task list [--daily|--path PATH]"
        " [--todo|--done] [--verbose] [--format text|json]",
        summary="List tasks.",
        json_output=True,
    ),
    CommandSpec(
        path=("task", "toggle"),
        usage="wikimason task toggle PATH LINE [--format text|json]",
        summary="Toggle task status.",
        json_output=True,
    ),
    CommandSpec(
        path=("task", "set"),
        usage="wikimason task set PATH LINE --status STATUS [--format text|json]",
        summary="Set task status.",
        json_output=True,
    ),
    # -- template --
    CommandSpec(
        path=("template",),
        usage="wikimason template [COMMAND] [--help]",
        summary="Template operations.",
    ),
    CommandSpec(
        path=("template", "list"),
        usage="wikimason template list [--total] [--format text|json]",
        summary="List templates.",
        json_output=True,
    ),
    CommandSpec(
        path=("template", "read"),
        usage="wikimason template read NAME [--format text|json]",
        summary="Read a template.",
        json_output=True,
    ),
    CommandSpec(
        path=("template", "render"),
        usage="wikimason template render NAME --title TITLE [--format text|json]",
        summary="Render a template.",
        json_output=True,
    ),
    # -- text --
    CommandSpec(
        path=("text",),
        usage="wikimason text [COMMAND] [--help]",
        summary="Text analysis commands.",
    ),
    CommandSpec(
        path=("text", "wordcount"),
        usage="wikimason text wordcount PATH [--words|--characters] [--format text|json]",  # noqa: E501
        summary="Word count.",
        json_output=True,
    ),
    CommandSpec(
        path=("text", "outline"),
        usage="wikimason text outline PATH [--format text|json]",
        summary="Text outline.",
        json_output=True,
    ),
    # -- vault --
    CommandSpec(
        path=("vault",),
        usage="wikimason vault [COMMAND] [--help]",
        summary="Vault management commands.",
    ),
    CommandSpec(
        path=("vault", "init"),
        usage="wikimason vault init [PATH] [--profile PROFILE] [--demo] [--env NAME] [--format text|json]",  # noqa: E501
        summary="Initialize a vault.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "list"),
        usage="wikimason vault list [--total] [--format text|json]",
        summary="List registered vaults.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "register"),
        usage="wikimason vault register NAME PATH [--format text|json]",
        summary="Register a vault.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "doctor"),
        usage="wikimason vault doctor [--format text|json]",
        summary="Run vault doctor checks.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "build"),
        usage="wikimason vault build [--format text|json]",
        summary="Build vault indexes and catalog.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "lint"),
        usage="wikimason vault lint [--strict] [--format text|json]",
        summary="Lint vault.",
        json_output=True,
    ),
    CommandSpec(
        path=("vault", "maintain"),
        usage="wikimason vault maintain [--log TEXT] [--format text|json]",
        summary="Full vault maintenance.",
        json_output=True,
    ),
    # -- query --
    CommandSpec(
        path=("query",),
        usage="wikimason query QUERY [--tag TAG] [--vault PATH] [--format text|json]",
        summary="Query the built catalog with a neutral top-level search command.",
        json_output=True,
    ),
    # -- page --
    CommandSpec(
        path=("page",),
        usage="wikimason page [COMMAND] [--help]",
        summary="Compiled page operations.",
    ),
    CommandSpec(
        path=("page", "create"),
        usage="wikimason page create --kind KIND --title TITLE"
        " [--source PATH ...] [--related PATH ...]"
        " [--status STATUS] [--summary TEXT]"
        " [--body TEXT] [--body-file PATH] [--path PATH] [--dry-run] [--print] [--allow-incomplete]"  # noqa: E501
        " [--vault PATH] [--format text|json]",
        summary="Create a compiled wiki page using the neutral page command surface.",
        json_output=True,
    ),
    CommandSpec(
        path=("page", "show"),
        usage="wikimason page show PATH [--format text|json]",
        summary="Read a compiled wiki page from the current root.",
        json_output=True,
    ),
    CommandSpec(
        path=("page", "update"),
        usage="wikimason page update PATH [--content TEXT|--body TEXT|--body-file PATH] [--format text|json]",  # noqa: E501
        summary="Overwrite a compiled wiki page body or full content deterministically.",  # noqa: E501
        json_output=True,
    ),
    CommandSpec(
        path=("page", "move"),
        usage="wikimason page move OLD NEW [--format text|json]",
        summary="Move a compiled wiki page within the active root.",
        json_output=True,
    ),
    CommandSpec(
        path=("page", "delete"),
        usage="wikimason page delete PATH [--permanent] [--format text|json]",
        summary="Delete a compiled wiki page permanently or via .trash.",
        json_output=True,
    ),
    # -- index --
    CommandSpec(
        path=("index",),
        usage="wikimason index [COMMAND] [--help]",
        summary="Index maintenance commands.",
    ),
    CommandSpec(
        path=("index", "build"),
        usage="wikimason index build [--vault PATH] [--format text|json]",
        summary="Rebuild derived index pages from the current catalog entries.",
        json_output=True,
    ),
    CommandSpec(
        path=("index", "check"),
        usage="wikimason index check [--vault PATH] [--format text|json]",
        summary="Check whether derived index pages are up to date.",
        json_output=True,
    ),
    # -- note --
    CommandSpec(
        path=("note",),
        usage="wikimason note [COMMAND] [--help]",
        summary="Note workflow commands.",
    ),
    CommandSpec(
        path=("note", "new"),
        usage="wikimason note new --kind KIND --title TITLE"
        " [--source PATH ...] [--related PATH ...]"
        " [--status STATUS] [--summary TEXT]"
        " [--body TEXT] [--body-file PATH] [--path PATH] [--dry-run] [--print] [--allow-incomplete]"  # noqa: E501
        " [--format text|json]",
        summary="Create a new note.",
        json_output=True,
    ),
    CommandSpec(
        path=("note", "validate"),
        usage="wikimason note validate PATH [--strict] [--format text|json]",
        summary="Validate a note.",
        json_output=True,
    ),
    CommandSpec(
        path=("note", "normalize"),
        usage="wikimason note normalize PATH [--fix] [--format text|json]",
        summary="Normalize a note.",
        json_output=True,
    ),
    # -- catalog --
    CommandSpec(
        path=("catalog",),
        usage="wikimason catalog [COMMAND] [--help]",
        summary="Catalog commands.",
    ),
    CommandSpec(
        path=("catalog", "search"),
        usage="wikimason catalog search QUERY|--query QUERY"
        " [--tag TAG] [--format text|json]",
        summary="Search the catalog.",
        json_output=True,
    ),
    CommandSpec(
        path=("catalog", "build"),
        usage="wikimason catalog build [--format text|json]",
        summary="Build the catalog.",
        json_output=True,
    ),
    CommandSpec(
        path=("catalog", "check"),
        usage="wikimason catalog check [--format text|json]",
        summary="Check catalog freshness.",
        json_output=True,
    ),
    CommandSpec(
        path=("catalog", "rebuild"),
        usage="wikimason catalog rebuild [--format text|json]",
        summary="Rebuild catalog and indexes.",
        json_output=True,
    ),
    # -- links --
    CommandSpec(
        path=("links",),
        usage="wikimason links [COMMAND] [--help]",
        summary="Link operations.",
    ),
    CommandSpec(
        path=("links", "resolve"),
        usage="wikimason links resolve QUERY [--format text|json]",
        summary="Resolve link matches.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "check"),
        usage="wikimason links check [--format text|json]",
        summary="Check for broken links.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "normalize"),
        usage="wikimason links normalize PATH [--fix] [--format text|json]",
        summary="Normalize links.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "outgoing"),
        usage="wikimason links outgoing PATH [--total] [--format text|json]",
        summary="Show outgoing links.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "backlinks"),
        usage="wikimason links backlinks PATH [--total] [--format text|json]",
        summary="Show backlinks.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "unresolved"),
        usage="wikimason links unresolved [--format text|json]",
        summary="List unresolved links.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "orphans"),
        usage="wikimason links orphans [--format text|json]",
        summary="List orphan notes.",
        json_output=True,
    ),
    CommandSpec(
        path=("links", "deadends"),
        usage="wikimason links deadends [--format text|json]",
        summary="List dead-end notes.",
        json_output=True,
    ),
    # -- ingest --
    CommandSpec(
        path=("ingest",),
        usage="wikimason ingest [--format text|json]",
        summary="Summarize ingest readiness and the next required wiki action.",
        json_output=True,
    ),
    CommandSpec(
        path=("ingest", "status"),
        usage="wikimason ingest status [--format text|json]",
        summary="Show ingest status.",
        json_output=True,
    ),
    CommandSpec(
        path=("ingest", "plan"),
        usage="wikimason ingest plan [SOURCE ...] [--format text|json]",
        summary="Plan ingest.",
        json_output=True,
    ),
    CommandSpec(
        path=("ingest", "finish"),
        usage="wikimason ingest finish [--accept-covered] [--scope changed|all] [--source PATH] [--format text|json]",  # noqa: E501
        summary="Finish ingest.",
        json_output=True,
    ),
    # -- top-level convenience --
    CommandSpec(
        path=("lint",),
        usage="wikimason lint [--strict] [--format text|json]",
        summary="Lint compiled pages.",
        json_output=True,
    ),
    CommandSpec(
        path=("status",),
        usage="wikimason status [--format text|json]",
        summary="Summarize vault readiness.",
        json_output=True,
    ),
    CommandSpec(
        path=("doctor",),
        usage="wikimason doctor [--format text|json]",
        summary="Run vault doctor checks.",
        json_output=True,
    ),
    CommandSpec(
        path=("log",),
        usage="wikimason log --title TITLE --details DETAILS [--format text|json]",
        summary="Append a log entry.",
        json_output=True,
    ),
    CommandSpec(
        path=("audit",),
        usage="wikimason audit [--format text|json]",
        summary="Audit vault.",
        json_output=True,
    ),
    # -- agents --
    CommandSpec(
        path=("agents",),
        usage="wikimason agents [COMMAND] [--help]",
        summary="Agent file management commands.",
    ),
    CommandSpec(
        path=("agents", "compile"),
        usage="wikimason agents compile [--check] [--format text|json]",
        summary="Compile AGENTS.md.",
        json_output=True,
    ),
    CommandSpec(
        path=("agents", "check"),
        usage="wikimason agents check [--format text|json]",
        summary="Check AGENTS.md freshness.",
        json_output=True,
    ),
    # -- skill --
    CommandSpec(
        path=("skill",),
        usage="wikimason skill [COMMAND] [--help]",
        summary="Skill commands.",
    ),
    CommandSpec(
        path=("skill", "path"),
        usage="wikimason skill path [--format text|json]",
        summary="Show skill path.",
        json_output=True,
    ),
    CommandSpec(
        path=("skill", "install"),
        usage="wikimason skill install --target PATH [--symlink] [--format text|json]",
        summary="Install skill.",
        json_output=True,
    ),
    # -- review --
    CommandSpec(
        path=("review",),
        usage="wikimason review [COMMAND] [--help]",
        summary="Review queue commands.",
        json_output=True,
    ),
    CommandSpec(
        path=("review", "list"),
        usage="wikimason review list [--format text|json]",
        summary="List review queue items.",
        json_output=True,
    ),
    CommandSpec(
        path=("review", "show"),
        usage="wikimason review show ID [--format text|json]",
        summary="Show one review queue item.",
        json_output=True,
    ),
    CommandSpec(
        path=("review", "resolve"),
        usage="wikimason review resolve ID --status accepted|skipped|done [--format text|json]",  # noqa: E501
        summary="Mark a review queue item resolved.",
        json_output=True,
    ),
    CommandSpec(
        path=("review", "add"),
        usage="wikimason review add --kind KIND --title TEXT [--detail TEXT] [--source-id ID] [--format text|json]",  # noqa: E501
        summary="Add a review queue item.",
        json_output=True,
    ),
)
