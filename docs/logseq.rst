Logseq Profile
==============


The Logseq profile makes WikiMason work with Logseq graph directories.

Path mapping
------------


Logseq stores pages flat in `pages/`. Namespaces are encoded into filenames:


PageRef("Wiki/Tech/Strapi")  ->  pages/Wiki___Tech___Strapi.md
pages/Wiki___Tech___Strapi.md  ->  PageRef("Wiki/Tech/Strapi")


The namespace separator defaults to `___` (triple underscore) and can be
configured in `[profile.logseq]`.

Metadata format
---------------


Logseq uses `property:: value` lines at the top of each page:


* type:: knowledge
* domain:: tech
* confidence:: high
* created:: 2026-05-29
* updated:: 2026-05-29

* ## Deployment Pipeline
  * CI/CD workflow for production.


Properties are parsed from the top of the file until a non-property block is
encountered. Lists (`tags`, `sources`, `topics`, `aliases`) use comma-separated
values.

Body rendering
--------------


The Logseq profile converts internal standard Markdown to outliner blocks:

* Headings: `- ## Heading` (nested)
* Lists: nested with block depth
* Code fences: preserved as child blocks
* Tables: nested under a parent block

**Limitations**: Tables and code blocks inside Logseq pages may not display
correctly in the Logseq editor. Use with caution.

Init layout
-----------


`wikimason init logseq` creates:


pages/
  Wiki___index.md
  Wiki___Dashboard.md
  Wiki___Tech.md
  Wiki___Projects.md
  Wiki___Schema.md
journals/             (optional)
Raw/Sources/
Schema/
_templates/
AGENTS.md
wikimason.toml


Migration
---------


Migrate from Logseq to another profile:

.. code-block:: bash

wikimason migrate logseq-to-obsidian --from ./logseq-graph --to ./obsidian-vault
wikimason migrate logseq-to-markdown --from ./logseq-graph --to ./md-vault

