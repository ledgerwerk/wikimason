Command Reference
=================

This landing page mirrors the generated Markdown reference in
``docs/command-reference.md``.

WikiMason exposes canonical filesystem-backed command groups together with
retained migration aliases. Prefer the generated Markdown reference for the
current command list and usage strings.

Vault
-----

``vault init``
~~~~~~~~~~~~~~

- Usage: ``wikimason vault init [PATH] [--tool obsidian|markdown] [--env NAME] [--demo]``
- Summary: Initialize a wiki root and seed the starter layout.
- JSON output: no
- Aliases: ``wikimason init``

``vault doctor``
~~~~~~~~~~~~~~~~

- Usage: ``wikimason vault doctor [--vault PATH] [--format text|json]``
- Summary: Check the vault layout, source manifest, and compiled note health.
- JSON output: yes
- Aliases: ``wikimason doctor``

``vault build``
~~~~~~~~~~~~~~~

- Usage: ``wikimason vault build [--vault PATH] [--format text|json]``
- Summary: Rebuild source counts, the catalog, and section indexes.
- JSON output: yes
- Aliases: ``wikimason build``

``vault lint``
~~~~~~~~~~~~~~

- Usage: ``wikimason vault lint [--vault PATH] [--strict] [--format text|json]``
- Summary: Lint compiled notes and optionally enforce strict draft checks.
- JSON output: yes
- Aliases: ``wikimason lint``, ``wikimason lint-staged``

``vault maintain``
~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason vault maintain [--vault PATH] [--log TEXT] [--format text|json]``
- Summary: Run the maintenance workflow across doctor, build, lint, source, and audit checks.
- JSON output: yes
- Aliases: ``wikimason maintain``

Source
------

``source add``
~~~~~~~~~~~~~~

- Usage: ``wikimason source add PATH [--vault PATH] [--move]``
- Summary: Copy or move a raw source into Raw/Sources/ and seed frontmatter when needed.
- JSON output: yes

``source list``
~~~~~~~~~~~~~~~

- Usage: ``wikimason source list [--vault PATH] [--format text|json]``
- Summary: List raw sources currently present in the vault.
- JSON output: yes

``source resolve``
~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason source resolve QUERY [--vault PATH] [--format text|json]``
- Summary: Resolve a human-entered source query to exact Raw/Sources path candidates.
- JSON output: yes

``source scan``
~~~~~~~~~~~~~~~

- Usage: ``wikimason source scan [--vault PATH] [--update] [--accept-covered] [--format text|json]``
- Summary: Scan raw sources, optionally update the manifest, and record covered sources.
- JSON output: yes
- Aliases: ``wikimason source-scan``

``source delta``
~~~~~~~~~~~~~~~~

- Usage: ``wikimason source delta [--vault PATH] [--format text|json]``
- Summary: Report actionable source changes and preserve exit code 2 when work remains.
- JSON output: yes
- Aliases: ``wikimason source-delta``

``source coverage``
~~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason source coverage [PATH] [--vault PATH] [--format text|json]``
- Summary: Report raw-source coverage across compiled notes.
- JSON output: yes
- Aliases: ``wikimason source-coverage``

``source lint``
~~~~~~~~~~~~~~~

- Usage: ``wikimason source lint [--vault PATH] [--format text|json]``
- Summary: Validate the source manifest and source-coverage bookkeeping.
- JSON output: yes
- Aliases: ``wikimason source-lint``

Note
----

``note new``
~~~~~~~~~~~~

- Usage: ``wikimason note new --kind KIND --title TITLE [--source PATH ...] [--related PATH ...] [--status STATUS] [--summary TEXT] [--body-file PATH] [--allow-incomplete] [--vault PATH] [--format text|json]``
- Summary: Create a compiled note scaffold with exact raw-source paths and normalized related links.
- JSON output: yes

``note validate``
~~~~~~~~~~~~~~~~~

- Usage: ``wikimason note validate PATH [--vault PATH] [--strict] [--format text|json]``
- Summary: Lint a single compiled note using the same checks as vault lint.
- JSON output: yes

``note normalize``
~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason note normalize PATH [--vault PATH] [--fix] [--format text|json]``
- Summary: Normalize a note scaffold and optionally rewrite links to canonical forms.
- JSON output: yes

Catalog
-------

``catalog search``
~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason catalog search --query QUERY [--tag TAG] [--vault PATH] [--format text|json]``
- Summary: Search the built catalog by title, aliases, summary, tags, and paths.
- JSON output: yes
- Aliases: ``wikimason search-catalog``, ``wikimason search``

``catalog rebuild``
~~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason catalog rebuild [--vault PATH] [--format text|json]``
- Summary: Rebuild the catalog and section indexes without changing the canonical build path.
- JSON output: yes

Links
-----

``links check``
~~~~~~~~~~~~~~~

- Usage: ``wikimason links check [--vault PATH] [--format text|json]``
- Summary: Report unresolved body links with line numbers and suggested canonical replacements.
- JSON output: yes

``links resolve``
~~~~~~~~~~~~~~~~~

- Usage: ``wikimason links resolve QUERY [--vault PATH] [--format text|json]``
- Summary: Resolve a title, alias, stem, or path to canonical link candidates for the active profile.
- JSON output: yes

``links normalize``
~~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason links normalize PATH [--vault PATH] [--fix] [--format text|json]``
- Summary: Inspect or rewrite ambiguous body links to canonical profile-aware link syntax.
- JSON output: yes

Ingest
------

``ingest status``
~~~~~~~~~~~~~~~~~

- Usage: ``wikimason ingest status [--vault PATH] [--format text|json]``
- Summary: Summarize first-run readiness across doctor, lint, source delta, and coverage.
- JSON output: yes

``ingest plan``
~~~~~~~~~~~~~~~

- Usage: ``wikimason ingest plan [SOURCE ...] [--vault PATH] [--format text|json]``
- Summary: Return deterministic source-to-note path hints and required validation commands.
- JSON output: yes

``ingest finish``
~~~~~~~~~~~~~~~~~

- Usage: ``wikimason ingest finish [--vault PATH] [--accept-covered] [--format text|json]``
- Summary: Run the final ingest validation pipeline and preserve exit code 2 when source work remains.
- JSON output: yes

Skill
-----

``skill path``
~~~~~~~~~~~~~~

- Usage: ``wikimason skill path``
- Summary: Print the packaged WikiMason skill path.
- JSON output: no

``skill install``
~~~~~~~~~~~~~~~~~

- Usage: ``wikimason skill install --target PATH [--symlink]``
- Summary: Install the packaged WikiMason skill into another target directory.
- JSON output: no

Agents
------

``agents compile``
~~~~~~~~~~~~~~~~~~

- Usage: ``wikimason agents compile [--vault PATH] [--check] [--format text|json]``
- Summary: Compile AGENTS.md from Schema policy, schema config, command metadata, and templates.
- JSON output: yes

Log
---

``log``
~~~~~~~

- Usage: ``wikimason log --title TITLE --details DETAILS [--vault PATH]``
- Summary: Append an operational log note.
- JSON output: no

Audit
-----

``audit``
~~~~~~~~~

- Usage: ``wikimason audit [--vault PATH] [--json]``
- Summary: Run the vault audit checks.
- JSON output: yes
