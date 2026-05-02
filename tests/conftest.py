"""
Shared pytest fixtures.
All external services (S3, Snowflake, Prefect) are mocked.
Unit tests never make real network calls.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import Settings


FAKE_SETTINGS = Settings(
    aws_access_key_id     = "fake_key",
    aws_secret_access_key = "fake_secret",
    aws_region            = "us-east-1",
    s3_bucket_name        = "rentwise-raw",
    snowflake_account     = "fake_account",
    snowflake_user        = "fake_user",
    snowflake_password    = "fake_password",
    snowflake_database    = "RENTWISE_DB",
    snowflake_warehouse   = "RENTWISE_WH",
    snowflake_role        = "SYSADMIN",
    snowflake_raw_schema  = "RAW",
    prefect_api_key       = "fake_prefect_key",
)


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("config.get_settings", return_value=FAKE_SETTINGS):
        with patch("scrapers.privateproperty.get_settings", return_value=FAKE_SETTINGS):
            with patch("pipeline.snowflake_load.get_settings", return_value=FAKE_SETTINGS):
                yield


SAMPLE_RAW_LISTINGS = [
    {
        "url":         "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/claremont/RR123456",
        "listing_id":  "PP_RR123456",
        "title":       "Modern 2 Bed Apartment in Claremont",
        "price":       "R 15 500",
        "price_raw":   "R 15 500",
        "suburb":      "Claremont",
        "address":     "10 Main Road, Claremont",
        "city":        "Cape Town",
        "latitude":    -33.9806,
        "longitude":   18.4655,
        "geo_source":  "direct",
        "bedrooms":    "2",
        "bathrooms":   "1",
        "parking":     "1",
        "agent":       "John Smith",
        "source_page": "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55",
        "scraped_at":  datetime.now(timezone.utc),
    },
    {
        "url":         "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/obs/RR789012",
        "listing_id":  "PP_RR789012",
        "title":       "Cosy 1 Bed Flat in Observatory",
        "price":       "R 9 800",
        "price_raw":   "R 9 800",
        "suburb":      "Observatory",
        "address":     "5 Lower Main Road, Observatory",
        "city":        "Cape Town",
        "latitude":    None,
        "longitude":   None,
        "geo_source":  "unknown",
        "bedrooms":    "1",
        "bathrooms":   "1",
        "parking":     "0",
        "agent":       None,
        "source_page": "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55",
        "scraped_at":  datetime.now(timezone.utc),
    },
]


@pytest.fixture
def sample_raw_listings():
    return SAMPLE_RAW_LISTINGS.copy()


@pytest.fixture
def sample_dataframe():
    return pd.DataFrame(SAMPLE_RAW_LISTINGS)


@pytest.fixture
def mock_s3_client(mocker):
    mock = MagicMock()
    mocker.patch("boto3.client", return_value=mock)
    return mock


@pytest.fixture
def mock_snowflake_conn(mocker):
    mock_conn = MagicMock()
    mock_cur  = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = ("file.parquet", "LOADED", 0, 2, 0, 0, None, None)
    mocker.patch("snowflake.connector.connect", return_value=mock_conn)
    return mock_conn, mock_cur
