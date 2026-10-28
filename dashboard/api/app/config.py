from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "air_quality_dw"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    # Optional extra exact origins (comma-separated). Local Vite ports covered by regex.
    cors_origins: str = ""
    # Any localhost / 127.0.0.1 port (Vite may land on 5173–5180+).
    # Prefer [0-9] / [.] so Docker Compose env defaults do not over-escape \\d.
    cors_origin_regex: str = r"https?://(localhost|127[.]0[.]0[.]1)(:[0-9]+)?$"
    # In-memory GET response cache (app/cache.py); 0 turns it off.
    response_cache_mb: int = 128
    # How often to re-check whether the mart/dwh tables changed (cache cleared if so).
    response_cache_check_seconds: float = 15.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
