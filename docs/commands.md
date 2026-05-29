# Command Reference

WikiMason uses a neutral command vocabulary across all profiles. There is no
obsidian-specific or logseq-specific command set.

## Initialisation

```bash
wikimason init markdown [PATH]    # Generic Markdown wiki
wikimason init obsidian [PATH]    # Obsidian-compatible vault
wikimason init logseq [PATH]      # Logseq graph
```

## Source management

```bash
wikimason source add <path>             # Import a source file
wikimason source list                     # List source files
wikimason source show <id-or-path>        # Show source details
wikimason source verify                   # Verify source integrity
wikimason source lint                     # Check manifest integrity
wikimason source rehash                   # Recompute hashes
wikimason source migrate-frontmatter      # Upgrade old frontmatter
```

## Page operations

```bash
wikimason page create --kind KIND --title TITLE
wikimason page show <path>
wikimason page update <path> --content TEXT
wikimason page move <old> <new>
wikimason page delete <path>
```

## Index and catalog

```bash
wikimason index build    # Rebuild index pages
wikimason index check    # Check if indexes are current
wikimason catalog build  # Rebuild catalog
wikimason catalog check  # Check if catalog is current
```

## Query and ingest

```bash
wikimason query <query>     # Search the catalog
wikimason ingest            # Summarize ingest readiness
```

## Lint and status

```bash
wikimason lint              # Lint compiled pages
wikimason status            # Overall vault health
```

## AGENTS

```bash
wikimason agents compile    # Generate AGENTS.md from schema/templates/config
wikimason agents check      # Check if AGENTS.md is current
```

## Migration

```bash
wikimason migrate logseq-to-obsidian --from PATH --to PATH
wikimason migrate obsidian-to-logseq --from PATH --to PATH
wikimason migrate markdown-to-logseq --from PATH --to PATH
wikimason migrate logseq-to-markdown --from PATH --to PATH
```

## Vault administration

```bash
wikimason config show        # Show active config
wikimason config edit        # Edit config
wikimason config validate    # Validate config
wikimason config migrate     # Write config for existing root
wikimason doctor             # Run vault diagnostics
```

## File utilities

```bash
wikimason file list [path]
wikimason file read <path>
wikimason file write <path> --content TEXT
wikimason file append <path> --content TEXT
wikimason file prepend <path> --content TEXT
wikimason file move <old> <new>
wikimason file rename <old> <new>
wikimason file delete <path>
```

## Aliases (hidden, deprecated)

For backward compatibility, some commands have hidden aliases:

- `wikimason init` → `wikimason vault init`
- `wikimason lint` → `wikimason vault lint`
- `wikimason build` → `wikimason vault build`
- `wikimason doctor` → `wikimason vault doctor`
- `wikimason source-scan`, `source-delta`, `source-coverage` (old hyphenated forms)
