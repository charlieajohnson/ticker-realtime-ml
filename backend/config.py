"""Application settings loaded from environment / .env file."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Data provider
    api_provider: str = "synthetic"
    alpha_vantage_api_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None

    # Symbols
    symbols: str = "AAPL,GOOGL,MSFT,AMZN,NVDA,TSLA,META,JPM"

    # Pipeline
    ingest_interval_s: float = 10.0
    feature_window_size: int = 60
    inference_interval_s: float = 5.0

    # Database
    duckdb_path: str = "data/ticker.db"

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
