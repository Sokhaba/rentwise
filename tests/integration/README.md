# Integration tests

Require real credentials — NOT run in CI. Run locally before major releases.

## Prerequisites
- .env filled in with real values
- Snowflake RENTWISE_DB bootstrapped
- S3 bucket rentwise-raw accessible

## Running
pytest tests/integration/ -v
