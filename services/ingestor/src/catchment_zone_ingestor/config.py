"""Application settings, read from environment variables and config files.

Configuration is intentionally split in two: connection/runtime settings come
from the environment (see .env.example at the repo root), while the actual
source registries (which local authorities, which DfE publications, which
metric codes are valid) live in the version-controlled YAML files under
config/. Keeping the registries in YAML means adding a new pilot local
authority is a reviewable config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root, resolved relative to this file: services/ingestor/src/catchment_zone_ingestor/
# -> up 4 levels reaches the monorepo root where config/ lives.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CONFIG_DIR = _REPO_ROOT / "config"


class Settings(BaseSettings):
    """Runtime settings for the ingestion service.

    Reads INGEST_DATABASE_URL (never DATABASE_URL, which is the web app's
    lower-privilege or differently-scoped connection string) plus the paths
    to the source registry YAML files, which default to the monorepo's
    config/ directory but can be overridden for tests or local development.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ingest_database_url: str = Field(
        default="postgresql://school_ingestor:password@localhost:26257/school_intelligence",
        alias="INGEST_DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    config_dir: Path = Field(default=_DEFAULT_CONFIG_DIR)

    gias_download_override_url: str | None = Field(
        default=None,
        alias="GIAS_DOWNLOAD_OVERRIDE_URL",
        description=(
            "Manual override for the GIAS establishment extract download link, "
            "used when automatic discovery from the downloads page fails or the "
            "site's link pattern changes. See adapters/gias.py for the discovery "
            "logic this bypasses."
        ),
    )
    gias_trust_download_override_url: str | None = Field(
        default=None, alias="GIAS_TRUST_DOWNLOAD_OVERRIDE_URL"
    )

    http_timeout_seconds: float = Field(default=30.0, alias="INGEST_HTTP_TIMEOUT_SECONDS")
    batch_size: int = Field(
        default=1000,
        alias="INGEST_BATCH_SIZE",
        description="Row batch size for streaming CSV parsing and batch database upserts.",
    )

    @property
    def catchment_sources_path(self) -> Path:
        return self.config_dir / "catchment-sources.yml"

    @property
    def statistics_sources_path(self) -> Path:
        return self.config_dir / "statistics-sources.yml"

    @property
    def metric_definitions_path(self) -> Path:
        return self.config_dir / "metric-definitions.yml"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton, cached after first read."""
    return Settings()
