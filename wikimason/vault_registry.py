from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class VaultRegistry:
    path: Path

    @classmethod
    def default(cls) -> VaultRegistry:
        env_path = os.environ.get("WIKIMASON_REGISTRY_PATH")
        if env_path:
            return cls(Path(env_path))
        return cls(Path.home() / ".config" / "wikimason" / "vaults.json")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"last_used": None, "vaults": {}}
        result: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        return result

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )

    def register(self, name: str, path: Path, vault_id: str | None = None) -> None:
        data = self.load()
        vaults = data.setdefault("vaults", {})
        vaults[name] = {
            "path": str(path),
            "id": vault_id or name.lower().replace(" ", "-"),
        }
        data["last_used"] = name
        self.save(data)

    def set_last_used(self, name: str) -> None:
        data = self.load()
        data["last_used"] = name
        self.save(data)
