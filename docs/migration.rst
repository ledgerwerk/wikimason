Migration
=========


WikiMason provides profile-to-profile migration commands that convert pages
between markdown, obsidian, and logseq formats while preserving logical page
references, source identities, and content.

Commands
--------


.. code-block:: bash

wikimason migrate logseq-to-obsidian --from PATH --to PATH
wikimason migrate obsidian-to-logseq --from PATH --to PATH
wikimason migrate markdown-to-logseq --from PATH --to PATH
wikimason migrate logseq-to-markdown --from PATH --to PATH


What gets migrated
------------------


* All `.md` files (excluding operational files like `Schema/*`, `_templates/*`)
* Raw sources (`Raw/Sources/`) are copied unchanged
* Schema and template directories are copied
* The target config is written with the target profile
* Catalog and indexes are rebuilt

What is preserved
-----------------


* **Logical links**: `[[Wiki/Path/Page]]` references remain valid because all
  profiles use the same logical page reference model
* **Source IDs**: `source_id` values in the manifest remain unchanged
* **Content hashes**: `content_sha256` values remain the same
* **Original filenames**: `original_filename` is preserved

Migration workflow
------------------


.. code-block:: bash

1. Create a target directory
============================

mkdir ~/obsidian-vault

2. Migrate
==========

wikimason migrate logseq-to-obsidian \
  --from ~/Documents/Logseq/MyGraph \
  --to ~/obsidian-vault

3. Verify
=========

wikimason --vault ~/obsidian-vault source verify
wikimason --vault ~/obsidian-vault lint

