Wiki Profiles
=============

WikiMason supports three peer wiki profiles. The profile determines how pages
are stored on disk, how metadata is formatted, and how links are rendered.

.. list-table:: Built-in profiles
   :header-rows: 1

   * - Profile
     - Metadata
     - Body format
     - Page layout
   * - ``markdown``
     - YAML frontmatter
     - Standard Markdown
     - Nested directories
   * - ``obsidian``
     - YAML frontmatter
     - Standard Markdown
     - Nested directories
   * - ``logseq``
     - ``property::`` lines
     - Outliner blocks
     - Flat ``pages/`` directory

All profiles share the same logical page model, command vocabulary, and source
tracking. Switching profiles changes the on-disk layout without changing the
logical content.

Selecting a profile
-------------------

Initialise a new vault with a specific profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason init markdown [PATH]
   wikimason init obsidian [PATH]
   wikimason init logseq [PATH]

Check the active profile
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason config show --format json

Profile configuration
---------------------

Profiles can be overridden in ``wikimason.toml``:

.. code-block:: toml

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
