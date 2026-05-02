"""Unit tests for pipeline/snowflake_load.py"""

import pytest
from unittest.mock import patch


class TestLoadS3ToSnowflake:

    def test_skips_already_loaded_key(self, mock_snowflake_conn):
        mock_conn, mock_cur = mock_snowflake_conn
        mock_cur.fetchone.return_value = (1,)

        from pipeline.snowflake_load import load_s3_to_snowflake
        result = load_s3_to_snowflake("privateproperty/year=2026/listings.parquet")

        assert result == 0
        copy_calls = [c for c in mock_cur.execute.call_args_list if "COPY INTO" in str(c)]
        assert len(copy_calls) == 0

    def test_calls_copy_into_for_new_key(self, mock_snowflake_conn):
        mock_conn, mock_cur = mock_snowflake_conn
        mock_cur.fetchone.side_effect = [None, ("file.parquet", "LOADED", 0, 5, 0, 0, None, None)]

        from pipeline.snowflake_load import load_s3_to_snowflake
        result = load_s3_to_snowflake("privateproperty/year=2026/listings.parquet")

        assert result == 5

    def test_records_success_in_load_log(self, mock_snowflake_conn):
        mock_conn, mock_cur = mock_snowflake_conn
        mock_cur.fetchone.side_effect = [None, ("file.parquet", "LOADED", 0, 4, 0, 0, None, None)]

        from pipeline.snowflake_load import load_s3_to_snowflake
        load_s3_to_snowflake("privateproperty/year=2026/listings.parquet")

        insert_calls = [str(c) for c in mock_cur.execute.call_args_list
                        if "LOAD_LOG" in str(c) and "INSERT" in str(c)]
        assert len(insert_calls) >= 1
        assert any("success" in c for c in insert_calls)

    def test_records_error_status_on_failure(self, mock_snowflake_conn):
        mock_conn, mock_cur = mock_snowflake_conn
        mock_cur.fetchone.return_value = None
        mock_cur.execute.side_effect = [None, Exception("Snowflake error")]

        from pipeline.snowflake_load import load_s3_to_snowflake
        with pytest.raises(Exception):
            load_s3_to_snowflake("privateproperty/year=2026/listings.parquet")

        insert_calls = [str(c) for c in mock_cur.execute.call_args_list
                        if "LOAD_LOG" in str(c)]
        assert any("error" in c for c in insert_calls)
