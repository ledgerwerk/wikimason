Commands
========

WikiMason uses a neutral command vocabulary across all profiles. There
is no profile-specific command set.

Command families
----------------

=============  ===================================================================
Group          Purpose
=============  ===================================================================
``init``       Initialize a new wiki vault.
``config``     Show, edit, and validate TOML configuration.
``log``        Append, inspect, and validate the operational timeline in ``Wiki/log.md``.
``source``     Import, scan, verify, resolve, read, rehash, and lint raw sources.
``ingest``     Plan and finish raw-source-to-note workflows.
``note``       Create, validate, and normalize semantic notes.
``page``       Create, show, update, move, and delete profile-neutral pages.
``links``      Resolve, check, normalize, and inventory internal links.
``file``       Safe vault-relative file and folder operations.
``daily``      Daily notes and Markdown metadata utilities.
``catalog``    Build generated catalog, index pages, and ``AGENTS.md``.
``doctor``     Health, validation, and audit commands.
``vault``      Vault initialization, registry, build, lint, doctor, and maintenance.
``skill``      Locate or install the packaged WikiMason agent skill.
=============  ===================================================================

Example workflows
-----------------

Initialize a vault:

.. code-block:: bash

   wikimason init markdown .
   wikimason init obsidian ~/Documents/MyVault
   wikimason init logseq ~/Documents/Logseq/MyGraph

Source lifecycle:

.. code-block:: bash

   wikimason source scan --update --format json
   wikimason source delta --format json

Create compiled pages:

.. code-block:: bash

   wikimason note new --kind topic --title "Compiled Knowledge" \
     --source "Raw/Sources/report.md" --allow-incomplete --format json
   wikimason page update Wiki/Concepts/retrieval-pipeline.md --body-file /tmp/body.md --format json

Validate and finish:

.. code-block:: bash

   wikimason links check --format json
   wikimason ingest finish --accept-covered --format json

Maintain:

.. code-block:: bash

   wikimason vault maintain --format json
   wikimason log tail -n 5 --format json
   wikimason log check --format json

For the full command reference with every flag and usage string, see
:doc:`command-reference`.
