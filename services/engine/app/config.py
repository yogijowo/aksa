"""Configuration and OS-specific AppData directory resolution for AKSA Engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pydantic import BaseModel, Field


def get_default_appdata_dir() -> Path:
    """Resolve the cross-platform application data directory for AKSA."""
    env_override = os.environ.get("AKSA_APPDATA_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "com.aksa.desktop"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "com.aksa.desktop"
    else:
        return Path.home() / ".local" / "share" / "com.aksa.desktop"


class EngineConfig(BaseModel):
    """Runtime configuration for the AKSA Python FastAPI sidecar."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=43120)
    auth_token: str = Field(default="dev-aksa-local-token")
    dev_mode: bool = Field(default=True)
    appdata_dir: Path = Field(default_factory=get_default_appdata_dir)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    lmstudio_base_url: str = Field(default="http://127.0.0.1:1234/v1")

    @property
    def data_dir(self) -> Path:
        return self.appdata_dir / "data"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "aksa.db"

    @property
    def lancedb_dir(self) -> Path:
        return self.data_dir / "lancedb"

    @property
    def runtime_dir(self) -> Path:
        return self.appdata_dir / "runtime"

    @property
    def logs_dir(self) -> Path:
        return self.appdata_dir / "logs"

    def ensure_directories(self) -> None:
        """Create required application data subdirectories if they do not exist."""
        for directory in (self.appdata_dir, self.data_dir, self.lancedb_dir, self.runtime_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True)


settings = EngineConfig()

