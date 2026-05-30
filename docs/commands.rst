Command Reference
=================

WikiMason uses a neutral command vocabulary across all profiles. There
is no obsidian-specific or logseq-specific command set.

Initialisation
--------------

.. code:: bash

   wikimason init markdown [PATH]    # Generic Markdown wiki
   wikimason init obsidian [PATH]    # Obsidian-compatible vault
   wikimason init logseq [PATH]      # Logseq graph

Source management
-----------------

.. code:: bash

   wikimason source add <path>             # Import a source file
   wikimason source list                     # List source files
   wikimason source show <id-or-path>        # Show source details
   wikimason source verify                   # Verify source integrity
   wikimason source lint                     # Check manifest integrity
   wikimason source rehash                   # Recompute hashes

Page operations
---------------

.. code:: bash

   wikimason page create --kind KIND --title TITLE
   wikimason page show <path>
   wikimason page update <path> --content TEXT
   wikimason page move <old> <new>
   wikimason page delete <path>

Index and catalog
-----------------

.. code:: bash

   wikimason index build    # Rebuild index pages
   wikimason index check    # Check if indexes are current
   wikimason catalog build  # Rebuild catalog
   wikimason catalog check  # Check if catalog is current

Query and ingest
----------------

.. code:: bash

   wikimason query <query>     # Search the catalog
   wikimason ingest            # Summarize ingest readiness

Lint and status
---------------

.. code:: bash

   wikimason lint              # Lint compiled pages
   wikimason status            # Overall vault health

AGENTS
------

.. code:: bash

   wikimason agents compile    # Generate AGENTS.md from schema/templates/config
   wikimason agents check      # Check if AGENTS.md is current

Vault administration
--------------------

.. code:: bash

   wikimason config show        # Show active config
   wikimason config edit        # Edit config
   wikimason config validate    # Validate config
   wikimason doctor             # Run vault diagnostics

File utilities
--------------

.. code:: bash

   wikimason file list [path]
   wikimason file read <path>
   wikimason file write <path> --content TEXT
   wikimason file append <path> --content TEXT
   wikimason file prepend <path> --content TEXT
   wikimason file move <old> <new>
   wikimason file rename <old> <new>
   wikimason file delete <path>
