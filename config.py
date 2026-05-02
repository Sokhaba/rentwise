from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS
    aws_access_key_id:     str
    aws_secret_access_key: str
    aws_region:            str  = "us-east-1"
    s3_bucket_name:        str  = "rentwise-raw"

    # Snowflake
    snowflake_account:     str
    snowflake_user:        str
    snowflake_password:    str
    snowflake_database:    str  = "RENTWISE_DB"
    snowflake_warehouse:   str
    snowflake_role:        str  = "SYSADMIN"
    snowflake_raw_schema:  str  = "RAW"

    # Prefect
    prefect_api_key:       str  = ""

    # Local dev
    local_output_dir:      Path = Path("data/raw/privateproperty")

    model_config = {
        "env_file":          ".env",
        "env_file_encoding": "utf-8",
        "extra":             "ignore",   # silently ignore unknown env vars
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the Settings singleton.
    Lazy — only reads .env when first called, not on import.
    Cached — same instance returned on every subsequent call.

    Usage:
        from config import get_settings
        settings = get_settings()
    """
    return Settings()