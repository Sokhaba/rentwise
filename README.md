# RentWise

I built this to understand the Cape Town rental market properly not from 
listings I happened to scroll past, but from a full weekly snapshot of what's 
actually available and at what price. It scrapes Private Property every Sunday, 
runs through a Bronze/Silver/Gold Snowflake pipeline built with DBT, and lands 
in Power BI dashboards that show price benchmarks, how long listings sit before 
disappearing, and which ones have quietly dropped their asking price.

**Live pipeline:** Runs every Sunday 02:00 SAST via GitHub Actions

---

## Architecture

<!-- Add rentwise_architecture.svg here -->

---

## How it works

The scraper pulls all Cape Town rental listings from Private Property, validates 
every listing through Pydantic, and uploads a Parquet file to S3. From there loads it into Snowflake RAW, DBT cleans and transforms it through 
staging and intermediate layers, and lands it in a MART schema that Power BI 
reads directly. Each weekly run builds on the last tracking when listings 
first appeared, whether prices changed, and how long they've been active.

---

## Stack

| Layer | Tool |
|---|---|
| Scraping | Python · requests · BeautifulSoup |
| Validation | Pydantic v2 |
| Storage | AWS S3 Parquet, date-partitioned |
| Warehouse | Snowflake Bronze / Silver / Gold |
| Transformation | DBT Core |
| Orchestration | GitHub Actions cron |
| Dashboards | Power BI / Tableau |
| CI/CD | GitHub Actions lint · test · dbt compile |
| Tests | pytest 29 unit tests |

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in AWS, and Snowflake credentials
```

Bootstrap Snowflake by running `snowflake/setup.sql` in your worksheet,
load suburb centroids with `dbt seed`, then run the scraper locally:

```bash
python -m scrapers.privateproperty
```

See the [build guide](#) for full account setup and end-to-end walkthrough.
