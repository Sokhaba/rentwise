"""
Load a specific S3 parquet file into Snowflake RAW.LISTINGS_RAW.

Currently using AWS credentials directly in the COPY INTO statement.
This is a temporary approach — migrate to external stage (Option A)
when ready by following snowflake/setup.sql and the build guide Section 3.2.

TODO: migrate to external stage once S3 bucket is in af-south-1
"""

import snowflake.connector
from loguru import logger

from config import get_settings


def _get_conn():
    s = get_settings()
    return snowflake.connector.connect(
        account   = s.snowflake_account,
        user      = s.snowflake_user,
        password  = s.snowflake_password,
        database  = s.snowflake_database,
        schema    = s.snowflake_raw_schema,
        warehouse = s.snowflake_warehouse,
        role      = s.snowflake_role,
    )


def _already_loaded(cur, s3_key: str) -> bool:
    s = get_settings()
    cur.execute(
        f"SELECT 1 FROM {s.snowflake_database}.{s.snowflake_raw_schema}.LOAD_LOG "
        f"WHERE s3_key = %s AND status = 'success'",
        (s3_key,)
    )
    return cur.fetchone() is not None


def load_s3_to_snowflake(s3_key: str) -> int:
    """
    COPY parquet from S3 into LISTINGS_RAW using direct credentials.
    Returns rows loaded, or 0 if already loaded (idempotent).
    Raises on failure and records status in LOAD_LOG.
    """
    s    = get_settings()
    DB   = s.snowflake_database
    RAW  = s.snowflake_raw_schema
    conn = _get_conn()

    try:
        cur = conn.cursor()

        # ── Idempotency check ──────────────────────────────────
        if _already_loaded(cur, s3_key):
            logger.info(f"Skipping {s3_key} — already loaded")
            return 0

        # ── COPY INTO using direct credentials ─────────────────
        # TODO: replace with external stage once bucket is in af-south-1
        copy_sql = f"""
            COPY INTO {DB}.{RAW}.LISTINGS_RAW
            FROM 's3://{s.s3_bucket_name}/{s3_key}'
            CREDENTIALS = (
                AWS_KEY_ID     = '{s.aws_access_key_id}'
                AWS_SECRET_KEY = '{s.aws_secret_access_key}'
            )
            FILE_FORMAT = (
                TYPE               = 'PARQUET'
                SNAPPY_COMPRESSION = TRUE
            )
            MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
            ON_ERROR = 'CONTINUE'
            PURGE    = FALSE
        """
        cur.execute(copy_sql)
        result      = cur.fetchone()
        rows_loaded = int(result[3]) if result else 0

        # ── Record success in load log ─────────────────────────
        cur.execute(
            f"INSERT INTO {DB}.{RAW}.LOAD_LOG (s3_key, rows_loaded, status) "
            f"VALUES (%s, %s, 'success')",
            (s3_key, rows_loaded),
        )
        conn.commit()
        logger.info(f"Loaded {rows_loaded} rows from {s3_key}")
        return rows_loaded

    except Exception as e:
        try:
            cur.execute(
                f"INSERT INTO {DB}.{RAW}.LOAD_LOG (s3_key, rows_loaded, status) "
                f"VALUES (%s, 0, 'error')",
                (s3_key,),
            )
            conn.commit()
        except Exception:
            pass
        logger.error(f"Load failed for {s3_key}: {e}")
        raise

    finally:
        conn.close()
