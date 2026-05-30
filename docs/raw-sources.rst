Raw Sources
===========

Raw sources are the original input files stored under ``Raw/Sources/``. Every
source tracked by WikiMason carries metadata for identity, content integrity,
and provenance.

Source identity
---------------

Each source gets a stable **source ID** on first import:

.. code-block:: text

   src_<YYYYMMDD>_<sha256-prefix-12>

Example: ``src_20260529_7a91f04c2bb1``

The source ID never changes, even if the file is renamed or its content is
updated. It is the primary key in the manifest and the stable reference used
in wiki page citations.

Metadata storage
----------------

Text sources (.md)
~~~~~~~~~~~~~~~~~~

Text sources embed wikimason metadata as ``wm_``-prefixed keys in the YAML
frontmatter:

.. code-block:: yaml

   ---
   wm_source_id: src_20260529_8f3a1f1b
   wm_original_filename: "meeting-notes.md"
   wm_current_filename: "meeting-notes.md"
   wm_source_kind: text
   wm_content_sha256: "..."
   title: "My Source"
   ---

The ``wm_`` prefix namespace avoids collision with user metadata. These fields
are managed by WikiMason and should not be edited manually.

Binary sources (PDF, images, etc.)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Binary sources get a sidecar file:

.. code-block:: text

   Raw/Sources/report.pdf
   Raw/Sources/report.pdf.wikimason.json

The sidecar is a JSON file containing the same ``wm_`` fields as text sources.
For binary files, ``hash_scope`` is ``full_file_bytes``.

Content hashing
---------------

For text sources, the content hash is computed from the **body only** (after
removing the YAML frontmatter), normalized to LF line endings. This allows
metadata-only edits to not trigger content-change detection.

Manifest
--------

The source manifest is stored at ``Schema/source-manifest.jsonl``. It is keyed
by ``source_id`` (not path). One JSON line per source:

.. code-block:: json

   {"source_id": "src_20260529_8f3a1f1b", "path": "Raw/Sources/meeting-notes.md"}

Commands
--------

Add a source file
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason source add <path> --format json

List sources
~~~~~~~~~~~~

.. code-block:: bash

   wikimason source list --format json

Show source details
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason source show <source-id-or-path> --format json

Verify source integrity
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason source verify --format json

Recompute hashes from current file state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason source rehash --format json

Check source manifest integrity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   wikimason source lint --format json

Rename detection
----------------

``wikimason source verify`` detects renames by comparing ``source_id`` and
content hash. If a file moves to a new path but keeps the same source ID and
hash, it is reported as a rename rather than a new source.
