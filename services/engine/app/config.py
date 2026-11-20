"""Configuration and OS-specific AppData directory resolution for AKSA Engine."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from pydantic import BaseModel, Field


def _is_dev_mode() -> bool:
    dev_env = os.environ.get("AKSA_DEV_MODE")
    if dev_env is not None:
        return dev_env.lower() in ("1", "true", "yes")
    return os.environ.get("AKSA_ENV", "").lower() == "development"


def _resolve_auth_token(is_dev: bool) -> str:
    token = os.environ.get("AKSA_AUTH_TOKEN", "").strip()
    if is_dev:
        return token or "dev-aksa-local-token"
    # Production / Release mode:
    # Reject static development token or empty string; generate CSPRNG token if not supplied
    if not token or token == "dev-aksa-local-token":
        token = secrets.token_urlsafe(32)
    return token


def get_default_appdata_dir() -> Path:
    """Resolve the cross-platform application data directory for AKSA."""
    env_override = os.environ.get("AKSA_APPDATA_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if "pytest" in sys.modules or os.environ.get("AKSA_TESTING") == "1":
        import tempfile

        return (Path(tempfile.gettempdir()) / "aksa_pytest_appdata").resolve()

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
    dev_mode: bool = Field(default_factory=_is_dev_mode)
    testing: bool = Field(default_factory=lambda: "pytest" in sys.modules or os.environ.get("AKSA_TESTING") == "1")
    auth_token: str = Field(default="")
    appdata_dir: Path = Field(default_factory=get_default_appdata_dir)
    aksa_root_dir: Path | None = Field(default=None)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    lmstudio_base_url: str = Field(default="http://127.0.0.1:1234/v1")
    rag_embedding_mode: str = Field(default="lexical")  # lexical | ollama | onnx
    rag_ollama_model: str = Field(default="bge-m3")

    def model_post_init(self, __context: object) -> None:
        if not self.auth_token:
            self.auth_token = _resolve_auth_token(self.dev_mode)
        if self.aksa_root_dir is None:
            custom_root = os.environ.get("AKSA_ROOT_DIR")
            if custom_root:
                self.aksa_root_dir = Path(custom_root).expanduser().resolve()
            else:
                self.aksa_root_dir = self.appdata_dir / "aksa_root"

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

    def get_root_dir(self) -> Path:
        if self.aksa_root_dir is None:
            self.aksa_root_dir = self.appdata_dir / "aksa_root"
        return self.aksa_root_dir

    def ensure_directories(self) -> None:
        """Create required application data subdirectories if they do not exist."""
        for directory in (self.appdata_dir, self.data_dir, self.lancedb_dir, self.runtime_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if self.aksa_root_dir:
            self.aksa_root_dir.mkdir(parents=True, exist_ok=True)


settings = EngineConfig()

