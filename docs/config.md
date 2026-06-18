# Configuration

WikiMason configuration uses TOML files. Configuration is resolved in this
precedence order:

1. Explicit `--config /path/to/file.toml`
2. Local `wikimason.toml` (walked upwards from cwd)
3. `--env NAME` → `~/.config/wikimason/NAME.toml`
4. Default env `~/.config/wikimason/default.toml`
5. Built-in defaults

If both a local config and `--env` are present, the local config wins (it is
more specific to the project). A diagnostic is emitted when a local config
causes `--env` to be ignored.

## Example

```toml
config_version = 1

[wiki]
name = "my_wiki"
profile = "logseq"
root = "~/Documents/Logseq/MyGraph"

[paths]
raw = "Raw"
sources = "Raw/Sources"
files = "Raw/Files"
wiki = "Wiki"
schema = "Schema"
templates = "_templates"
agents = "AGENTS.md"

[links]
style = "wikilink"

[profile.logseq]
flat_pages = true
namespace_separator = "___"
property_style = "logseq"
pages_dir = "pages"

[profile.obsidian]
hub_filename = "_index.md"
nested_dirs = true
exclude = [".obsidian/workspace.json"]

[profile.markdown]
hub_filename = "index.md"
nested_dirs = true
```

## Commands

### Show the active config

```bash
wikimason config show --format json
```

### Open config in `$EDITOR`

```bash
wikimason config edit
```

### Validate config

```bash
wikimason config validate --format json
```

## Logging

WikiMason supports configurable operational logging and rotation.

```toml
[logging]
enabled = true
path = "Wiki/log.md"
mode = "normal"              # quiet | normal | diagnostic
min_level = "info"           # info | warning | error
include_audit_success = false
include_metadata = false
include_counts = "non_clean" # never | non_clean | always
max_summary_chars = 160
include_commands = []
exclude_commands = [
  "doctor",
  "vault.doctor",
  "links.check",
  "source.coverage",
  "ingest.plan",
]

[logging.rotation]
enabled = true
strategy = "size"            # none | size
max_bytes = 1048576
max_files = 5
archive_dir = "Wiki/logs"
```

Behavior:

1. `mode = "normal"` logs changes and actionable/problem states with compact entries.
2. `mode = "diagnostic"` logs full verbose audit/change entries (legacy shape).
3. `mode = "quiet"` logs only warnings/errors/actionable/problem outcomes.
4. `enabled = false` suppresses automatic logs, but `wikimason log add` still writes.
