"""
RentWise weekly pipeline — 3 stages.

  1. Scrape Private Property → validate row count → upload Parquet to S3
  2. Load Parquet from S3 into Snowflake RAW (idempotent via LOAD_LOG)
  3. Run DBT: stg_listings → int_listings_geo → mart_rental_prices → mart_suburb_benchmarks
"""

from datetime import datetime, timezone
from loguru import logger

from prefect import flow, task

from scrapers.privateproperty import run as scrape_pp
from pipeline.snowflake_load import load_s3_to_snowflake
from pipeline.dbt_runner import run_dbt

SCRAPE_ROW_MINIMUM = 50


@task(name="scrape-private-property", retries=2, retry_delay_seconds=600)
def task_scrape() -> str:
    logger.info("Starting Private Property scrape")
    df, s3_key = scrape_pp(upload=True)

    if not s3_key:
        raise ValueError("Scrape produced no S3 key — aborting pipeline")

    if len(df) < SCRAPE_ROW_MINIMUM:
        raise ValueError(
            f"Scrape returned only {len(df)} rows (minimum: {SCRAPE_ROW_MINIMUM}). "
            "Private Property HTML may have changed — check selectors."
        )

    logger.info(f"Scrape complete: {len(df)} rows → {s3_key}")
    return s3_key


@task(name="load-to-snowflake", retries=2, retry_delay_seconds=300)
def task_load_snowflake(s3_key: str) -> int:
    logger.info(f"Loading {s3_key} into Snowflake")
    rows = load_s3_to_snowflake(s3_key)
    logger.info(f"Loaded {rows} rows into Snowflake RAW")
    return rows


@task(name="run-dbt", retries=1, retry_delay_seconds=120)
def task_dbt() -> None:
    logger.info("Running DBT pipeline")
    run_dbt(select="staging+")
    logger.info("DBT run complete")


@flow(
    name="rentwise-weekly-pipeline",
    description="RentWise pipeline: scrape → S3 → Snowflake → DBT",
)
def rentwise_pipeline() -> dict:
    started_at = datetime.now(timezone.utc)
    logger.info(f"Pipeline started at {started_at.isoformat()}")

    s3_key      = task_scrape()
    rows_loaded = task_load_snowflake(s3_key)
    task_dbt()

    result = {
        "s3_key":       s3_key,
        "rows_loaded":  rows_loaded,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"Pipeline complete: {result}")
    return result


if __name__ == "__main__":
    rentwise_pipeline()
