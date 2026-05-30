# Command Reference

Public top-level commands for the neutral WikiMason CLI surface.

Global context options: `--config PATH`, `--env NAME`, `--vault PATH`.

## Init

### `init`

- Usage: `wikimason init [markdown|obsidian|logseq] [PATH] [--profile PROFILE] [--demo] [--env NAME] [--format text|json]`
- Summary: Initialize a new wiki vault.
- JSON output: yes

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

## Doctor

### `doctor`

- Usage: `wikimason doctor [--format text|json]`
- Summary: Run vault doctor checks.
- JSON output: yes

## Status

### `status`

- Usage: `wikimason status [--format text|json]`
- Summary: Summarize vault readiness.
- JSON output: yes

## Lint

### `lint`

- Usage: `wikimason lint [--strict] [--format text|json]`
- Summary: Lint compiled pages.
- JSON output: yes

## Source

### `source add`

- Usage: `wikimason source add PATH [--move] [--format text|json]`
- Summary: Add a raw source file.
- JSON output: yes

### `source list`

- Usage: `wikimason source list [--format text|json]`
- Summary: List raw source files.
- JSON output: yes

### `source resolve`

- Usage: `wikimason source resolve QUERY [--format text|json]`
- Summary: Resolve a source path by fuzzy query.
- JSON output: yes

### `source read`

- Usage: `wikimason source read QUERY [--lines N] [--first] [--format text|json]`
- Summary: Read a source file by path or fuzzy query.
- JSON output: yes

### `source show`

- Usage: `wikimason source show PATH [--vault PATH] [--format text|json]`
- Summary: Show one raw source plus its current manifest record.
- JSON output: yes

### `source scan`

- Usage: `wikimason source scan [--update] [--accept-covered] [--format text|json]`
- Summary: Scan raw sources and update manifest.
- JSON output: yes

### `source delta`

- Usage: `wikimason source delta [--check] [--format text|json]`
- Summary: Show delta between manifest and files.
- JSON output: yes

### `source coverage`

- Usage: `wikimason source coverage [PATH] [--format text|json]`
- Summary: Show source coverage report.
- JSON output: yes

### `source lint`

- Usage: `wikimason source lint [--format text|json]`
- Summary: Lint source manifest.
- JSON output: yes

### `source verify`

- Usage: `wikimason source verify [--strict] [--vault PATH] [--format text|json]`
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

### `ingest status`

- Usage: `wikimason ingest status [--format text|json]`
- Summary: Show ingest status.
- JSON output: yes

### `ingest plan`

- Usage: `wikimason ingest plan [SOURCE ...] [--format text|json]`
- Summary: Plan ingest.
- JSON output: yes

### `ingest finish`

- Usage: `wikimason ingest finish [--accept-covered] [--scope changed|all] [--source PATH] [--format text|json]`
- Summary: Finish ingest.
- JSON output: yes

## Note

### `note new`

- Usage: `wikimason note new --kind KIND --title TITLE [--source PATH ...] [--related PATH ...] [--status STATUS] [--summary TEXT] [--body TEXT] [--body-file PATH] [--path PATH] [--dry-run] [--print] [--allow-incomplete] [--format text|json]`
- Summary: Create a new note.
- JSON output: yes

### `note validate`

- Usage: `wikimason note validate PATH [--strict] [--format text|json]`
- Summary: Validate a note.
- JSON output: no

### `note normalize`

- Usage: `wikimason note normalize PATH [--fix] [--format text|json]`
- Summary: Normalize a note.
- JSON output: no

## Page

### `page create`

- Usage: `wikimason page create --kind KIND --title TITLE [--source PATH ...] [--related PATH ...] [--status STATUS] [--summary TEXT] [--body TEXT] [--body-file PATH] [--path PATH] [--dry-run] [--print] [--allow-incomplete] [--vault PATH] [--format text|json]`
- Summary: Create a compiled wiki page using the neutral page command surface.
- JSON output: yes

### `page show`

- Usage: `wikimason page show PATH [--format text|json]`
- Summary: Read a compiled wiki page from the current root.
- JSON output: yes

### `page update`

- Usage: `wikimason page update PATH [--content TEXT|--body TEXT|--body-file PATH] [--format text|json]`
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

## Links

### `links resolve`

- Usage: `wikimason links resolve QUERY [--format text|json]`
- Summary: Resolve link matches.
- JSON output: no

### `links check`

- Usage: `wikimason links check [--format text|json]`
- Summary: Check for broken links.
- JSON output: yes

### `links normalize`

- Usage: `wikimason links normalize PATH [--fix] [--format text|json]`
- Summary: Normalize links.
- JSON output: no

## File

### `file list`

- Usage: `wikimason file list [PATH] [--total] [--format text|json]`
- Summary: List files in the vault.
- JSON output: no

### `file read`

- Usage: `wikimason file read PATH [--format text|json]`
- Summary: Read a file.
- JSON output: no

### `file search`

- Usage: `wikimason file search --query QUERY [--path PATH] [--limit N] [--context] [--case] [--fuzzy] [--total] [--format text|json]`
- Summary: Search files for text.
- JSON output: no

## Review

### `review list`

- Usage: `wikimason review list [--format text|json]`
- Summary: List review queue items.
- JSON output: yes

### `review show`

- Usage: `wikimason review show ID [--format text|json]`
- Summary: Show one review queue item.
- JSON output: yes

### `review resolve`

- Usage: `wikimason review resolve ID --status accepted|skipped|done [--format text|json]`
- Summary: Mark a review queue item resolved.
- JSON output: yes

### `review add`

- Usage: `wikimason review add --kind KIND --title TEXT [--detail TEXT] [--source-id ID] [--format text|json]`
- Summary: Add a review queue item.
- JSON output: yes

## Vault

### `vault doctor`

- Usage: `wikimason vault doctor [--format text|json]`
- Summary: Run vault doctor checks.
- JSON output: yes

### `vault build`

- Usage: `wikimason vault build [--format text|json]`
- Summary: Build vault indexes and catalog.
- JSON output: no

### `vault lint`

- Usage: `wikimason vault lint [--strict] [--format text|json]`
- Summary: Lint vault.
- JSON output: no

### `vault maintain`

- Usage: `wikimason vault maintain [--log TEXT] [--format text|json]`
- Summary: Full vault maintenance.
- JSON output: no

## Query

### `query`

- Usage: `wikimason query QUERY [--tag TAG] [--vault PATH] [--format text|json]`
- Summary: Query the built catalog with a neutral top-level search command.
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

## Agents

### `agents compile`

- Usage: `wikimason agents compile [--check] [--format text|json]`
- Summary: Compile AGENTS.md.
- JSON output: yes

### `agents check`

- Usage: `wikimason agents check [--format text|json]`
- Summary: Check AGENTS.md freshness.
- JSON output: yes

## Skill

### `skill path`

- Usage: `wikimason skill path [--format text|json]`
- Summary: Show skill path.
- JSON output: yes

### `skill install`

- Usage: `wikimason skill install --target PATH [--symlink] [--format text|json]`
- Summary: Install skill.
- JSON output: yes
