from pathlib import Path

PROJECT_SKILL_PATH = Path("skills/wikimason/SKILL.md")
CORE_VAULT_DIRS = ("Raw", "Wiki", "Schema")
LOCAL_CONFIG_NAMES = (".wikimason.toml", "wikimason.toml")
DEFAULT_LOCAL_CONFIG_NAME = "wikimason.toml"
DEFAULT_TOOL_PROFILE = "markdown"
DEFAULT_PROFILE = DEFAULT_TOOL_PROFILE
GLOBAL_CONFIG_DIRNAME = Path(".config/wikimason")
SOURCE_SCHEMA_VERSION = 2
# Bumped from 1 at the ledgercore integration: binary sources now hash
# via true SHA-256 of file bytes (ledgercore.sha256_bytes) instead of
# sha256_text(raw_bytes.hex()). Migrate existing vaults with
# `wikimason source rehash --accept-covered`.
SOURCE_MANIFEST = Path("Schema/source-manifest.jsonl")
