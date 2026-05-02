"""Unit tests for pipeline/flows.py"""

import pandas as pd
import pytest
from unittest.mock import patch


class TestScrapeRowGuard:

    def test_raises_when_row_count_below_minimum(self):
        tiny_df = pd.DataFrame([{"listing_id": "PP_001"}] * 10)
        with patch("pipeline.flows.scrape_pp", return_value=(tiny_df, "s3://bucket/key.parquet")):
            from pipeline.flows import task_scrape
            with pytest.raises(ValueError, match="minimum"):
                task_scrape.fn()

    def test_passes_when_row_count_above_minimum(self):
        good_df = pd.DataFrame([{"listing_id": f"PP_{i:03d}"} for i in range(60)])
        with patch("pipeline.flows.scrape_pp", return_value=(good_df, "s3://bucket/key.parquet")):
            from pipeline.flows import task_scrape
            result = task_scrape.fn()
            assert result == "s3://bucket/key.parquet"

    def test_raises_when_no_s3_key_returned(self):
        good_df = pd.DataFrame([{"listing_id": f"PP_{i:03d}"} for i in range(60)])
        with patch("pipeline.flows.scrape_pp", return_value=(good_df, None)):
            from pipeline.flows import task_scrape
            with pytest.raises(ValueError, match="no S3 key"):
                task_scrape.fn()


class TestLoadSnowflakeTask:

    def test_passes_s3_key_to_loader(self):
        with patch("pipeline.flows.load_s3_to_snowflake", return_value=55) as mock_load:
            from pipeline.flows import task_load_snowflake
            result = task_load_snowflake.fn("privateproperty/year=2026/listings.parquet")
            mock_load.assert_called_once_with("privateproperty/year=2026/listings.parquet")
            assert result == 55


class TestDbtTask:

    def test_calls_dbt_build_with_staging_plus(self):
        with patch("pipeline.flows.run_dbt") as mock_dbt:
            from pipeline.flows import task_dbt
            task_dbt.fn()
            mock_dbt.assert_called_once_with(select="staging+")
