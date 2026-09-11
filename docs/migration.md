# Migration

WikiMason is currently a pre-release fresh-start CLI. Cross-profile migration
commands are intentionally not part of the public command surface yet.

If you need to move content between vault profiles, use explicit file-system
copy or conversion scripts in your own workflow, then run canonical verification

ledgercore's storage-migration API is not exposed by WikiMason because WikiMason vault content is not currently managed as ledgercore schema-3 storage. Vault/profile conversion and ledgercore storage relocation are separate concerns.
commands in the target vault:

```bash
wikimason source verify
wikimason index build
wikimason lint
```
