Agent Workflow
==============

This landing page mirrors the generated Markdown reference in
``docs/agent-workflow.md``.

Use the canonical top-level WikiMason commands for wiki workflows. The
product is filesystem-backed and does not expose a runtime bridge or a
``wikimason obsidian`` command namespace.

First-run workflow
------------------

1. ``wikimason vault doctor --format json``
2. ``wikimason source scan --update --format json``
3. ``wikimason source delta --format json``
4. ``wikimason ingest status --format json``
5. ``wikimason ingest plan --format json``
6. Draft semantic note bodies only after ``wikimason note new ...``
7. ``wikimason links check --format json``
8. ``wikimason ingest finish --accept-covered --format json``

Hard rules
----------

- Do not run upstream ``obsidian`` or ``obsidian-cli``.
- Do not run legacy starter scripts from older starter kits; translate old instructions into ``wikimason`` commands.
- Do not hand-edit generated catalog, index, or source-manifest files.
