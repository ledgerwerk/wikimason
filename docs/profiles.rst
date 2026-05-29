Wiki Profiles
=============


WikiMason supports three peer wiki profiles. The profile determines how pages
are stored on disk, how metadata is formatted, and how links are rendered.

| Profile    | Metadata         | Body format            | Page layout        |
| ---------- | ---------------- | ---------------------- | ------------------ |
| `markdown` | YAML frontmatter | Standard Markdown      | Nested directories |
| `obsidian` | YAML frontmatter | Standard Markdown      | Nested directories |
| `logseq`   | `property::`     | Outliner blocks (`- `) | Flat `pages/` dir  |

All profiles share the same logical page model, command vocabulary, and source
tracking. Switching profiles changes the on-disk layout without changing the
logical content.

Selecting a profile
-------------------


.. code-block:: bash

Initialise a new vault with a specific profile
==============================================

wikimason init markdown [PATH]
wikimason init obsidian [PATH]
wikimason init logseq [PATH]

Check the active profile
========================

wikimason config show


Profile configuration
---------------------


Profiles can be overridden in `wikimason.toml`:

.. code-block:: bash

[wiki]
profile = "logseq"

[profile.logseq]
flat_pages = true
property_style = "logseq"
outliner_prefix = "- "
pages_dir = "pages"

[profile.obsidian]
hub_filename = "_index.md"
exclude = [".obsidian/workspace.json"]

[profile.markdown]
hub_filename = "index.md"
pages_dir = "Wiki"

