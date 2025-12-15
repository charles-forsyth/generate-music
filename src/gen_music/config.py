import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Optional if using API Key
    project_id: Optional[str] = Field(None, description="Google Cloud Project ID")
    location: str = Field("us-central1", description="Google Cloud Location")
    model_id: str = Field(
        "models/lyria-realtime-exp", description="Vertex AI Model ID"
    )

    # Preferred: API Key
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.getcwd(), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    # Check for .env in home/config if not in current dir
    env_path_local = Path(os.getcwd()) / ".env"
    env_path_home = Path.home() / ".config" / "gen-music" / ".env"

    _env_file = []
    if env_path_home.exists():
        _env_file.append(env_path_home)
    if env_path_local.exists():
        _env_file.append(env_path_local)

    return Settings(_env_file=_env_file if _env_file else None)
