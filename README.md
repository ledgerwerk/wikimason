# WikiMason

Filesystem-backed CLI toolkit for building and maintaining an LLM wiki with
Obsidian, Markdown, or generic tool profiles.

## Install

```bash
python -m pip install -e '.[dev]'
```

## Commands

```bash
wikimason --help
wikimason vault doctor --format json
wikimason source scan --update --format json
wikimason source delta --format json
wikimason file list Wiki --format json
wikimason daily read --format json
wikimason note new --kind topic --title "Compiled Knowledge" --source Raw/Sources/example.md --allow-incomplete --format json
wikimason links check --format json
wikimason ingest status --format json
wikimason ingest plan --format json
wikimason ingest finish --accept-covered --format json
wikimason agents compile --check --format json
```

Legacy top-level commands such as `wikimason doctor`, `wikimason build`, `wikimason lint`, `wikimason source-scan`, and `wikimason source-delta` remain available as aliases, but the canonical noun/verb grammar above is the preferred agent workflow.

## Migration note

Old starter-kit material may mention `scripts/wiki_tool.py`, but that file is not part of WikiMason. Translate any such instructions into `wikimason ...` commands instead of trying to run the legacy script.

## Key design constraints

1. Single package at repository root (`wikimason/`), no `src/` layout.
2. Single project skill at `skills/wikimason/SKILL.md`.
3. Deterministic filesystem-backed command groups for wiki, file, daily, property, task, template, text, and link operations.
4. `AGENTS.md` is compiled from `Schema/` plus command/template metadata.
5. Runtime bridge commands are not part of the product surface.
