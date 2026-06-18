# Migration

WikiMason is currently a pre-release fresh-start CLI. Cross-profile migration
commands are intentionally not part of the public command surface yet.

If you need to move content between vault profiles, use explicit file-system
copy or conversion scripts in your own workflow, then run canonical verification
commands in the target vault:

```bash
wikimason source verify
wikimason index build
wikimason lint
```
