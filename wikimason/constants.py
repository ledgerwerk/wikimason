from pathlib import Path

PROJECT_SKILL_PATH = Path("skills/wikimason/SKILL.md")
CORE_VAULT_DIRS = ("Raw", "Wiki", "Schema")
LOCAL_CONFIG_NAMES = (".wikimason.toml", "wikimason.toml")
DEFAULT_LOCAL_CONFIG_NAME = "wikimason.toml"
DEFAULT_TOOL_PROFILE = "markdown"
DEFAULT_PROFILE = DEFAULT_TOOL_PROFILE
GLOBAL_CONFIG_DIRNAME = Path(".config/wikimason")
LEGACY_GLOBAL_ENV_DIRNAME = Path(".config/wikimason/envs")
SOURCE_SCHEMA_VERSION = 1
SOURCE_MANIFEST = Path("Schema/source-manifest.jsonl")
LEGACY_VAULT_SCHEMA_PATH = Path("Schema/wikimason.json")
VAULT_SCHEMA_PATH = LEGACY_VAULT_SCHEMA_PATH
