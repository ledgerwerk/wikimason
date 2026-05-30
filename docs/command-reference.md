# Command Reference

Public top-level commands for the neutral WikiMason CLI surface.

Global context options: `--config PATH`, `--env NAME`, `--vault PATH`.

## Config

### `config show`

- Usage: `wikimason config show [--format text|json]`
- Summary: Show the active config.
- JSON output: yes

### `config edit`

- Usage: `wikimason config edit`
- Summary: Open the active WikiMason config file in $EDITOR.
- JSON output: no

### `config validate`

- Usage: `wikimason config validate [--format text|json]`
- Summary: Validate the active config.
- JSON output: yes

## Source

### `source add`

- Usage: `wikimason source add PATH [--move] [--format text|json]`
- Summary: Add a raw source file.
- JSON output: no

### `source list`

- Usage: `wikimason source list [--format text|json]`
- Summary: List raw source files.
- JSON output: no

### `source show`

- Usage: `wikimason source show PATH [--vault PATH] [--format text|json]`
- Summary: Show one raw source plus its current manifest record.
- JSON output: yes

### `source verify`

- Usage: `wikimason source verify [--vault PATH] [--format text|json]`
- Summary: Verify raw-source state against the current manifest and coverage delta.
- JSON output: yes

### `source rehash`

- Usage: `wikimason source rehash [--vault PATH] [--accept-covered] [--format text|json]`
- Summary: Rewrite manifest hashes from the current raw-source files.
- JSON output: yes

## Ingest

### `ingest`

- Usage: `wikimason ingest [--format text|json]`
- Summary: Summarize ingest readiness and the next required wiki action.
- JSON output: yes

## Query

### `query`

- Usage: `wikimason query QUERY [--tag TAG] [--vault PATH] [--format text|json]`
- Summary: Query the built catalog with a neutral top-level search command.
- JSON output: yes

## Page

### `page create`

- Usage: `wikimason page create --kind KIND --title TITLE [--source PATH ...] [--related PATH ...] [--status STATUS] [--summary TEXT] [--body-file PATH] [--allow-incomplete] [--vault PATH] [--format text|json]`
- Summary: Create a compiled wiki page using the neutral page command surface.
- JSON output: yes

### `page show`

- Usage: `wikimason page show PATH [--format text|json]`
- Summary: Read a compiled wiki page from the current root.
- JSON output: yes

### `page update`

- Usage: `wikimason page update PATH --content TEXT [--format text|json]`
- Summary: Overwrite a compiled wiki page body or full content deterministically.
- JSON output: yes

### `page move`

- Usage: `wikimason page move OLD NEW [--format text|json]`
- Summary: Move a compiled wiki page within the active root.
- JSON output: yes

### `page delete`

- Usage: `wikimason page delete PATH [--permanent] [--format text|json]`
- Summary: Delete a compiled wiki page permanently or via .trash.
- JSON output: yes

## Index

### `index build`

- Usage: `wikimason index build [--vault PATH] [--format text|json]`
- Summary: Rebuild derived index pages from the current catalog entries.
- JSON output: yes

### `index check`

- Usage: `wikimason index check [--vault PATH] [--format text|json]`
- Summary: Check whether derived index pages are up to date.
- JSON output: yes

## Catalog

### `catalog build`

- Usage: `wikimason catalog build [--format text|json]`
- Summary: Build the catalog.
- JSON output: yes

### `catalog check`

- Usage: `wikimason catalog check [--format text|json]`
- Summary: Check catalog freshness.
- JSON output: yes

### `catalog search`

- Usage: `wikimason catalog search QUERY|--query QUERY [--tag TAG] [--format text|json]`
- Summary: Search the catalog.
- JSON output: yes

## Lint

### `lint`

- Usage: `wikimason lint [--strict] [--format text|json]`
- Summary: Lint compiled pages.
- JSON output: yes

## Status

### `status`

- Usage: `wikimason status [--format text|json]`
- Summary: Summarize vault readiness.
- JSON output: yes

## Agents

### `agents compile`

- Usage: `wikimason agents compile [--check] [--format text|json]`
- Summary: Compile AGENTS.md.
- JSON output: no

### `agents check`

- Usage: `wikimason agents check [--format text|json]`
- Summary: Check AGENTS.md freshness.
- JSON output: yes

## Doctor

### `doctor`

- Usage: `wikimason doctor [--format text|json]`
- Summary: Run vault doctor checks.
- JSON output: yes
