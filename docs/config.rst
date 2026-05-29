Configuration
=============


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

Example
-------


.. code-block:: bash

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

[profile.markdown]
hub_filename = "index.md"
nested_dirs = true


Commands
--------


.. code-block:: bash

Show the active config
======================

wikimason config show

Open config in $EDITOR
======================

wikimason config edit

Validate config
===============

wikimason config validate

Write config for an existing wiki root
======================================

wikimason config migrate [PATH] --profile markdown|obsidian|logseq

