import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
import hashlib
import boto3
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from pydantic import BaseModel, field_validator
from loguru import logger

from config import get_settings

logger.info("PrivateProperty scraper started")

# =====================
# CONFIG
# =====================
BASE_URL_TEMPLATE = (
    "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55"
    "?pt=House,ApartmentFlat,TownHouseCluster{page_suffix}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DELAY_SECONDS = 2
MAX_THREADS   = 5
BATCH_SIZE    = 100


# =====================
# PYDANTIC MODEL
# =====================
class Listing(BaseModel):
    platform:       str             = "privateproperty"
    listing_id:     str
    listing_number: Optional[str]   = None
    property_type:  Optional[str]   = None
    listing_date:   Optional[str]   = None
    title:          Optional[str]   = None
    price:          Optional[int]   = None
    price_raw:      Optional[str]   = None
    currency:       str             = "ZAR"
    suburb:         Optional[str]   = None
    address:        Optional[str]   = None
    city:           str             = "Cape Town"
    latitude:       Optional[float] = None
    longitude:      Optional[float] = None
    geo_source:     str             = "unknown"
    bedrooms:       Optional[int]   = None
    bathrooms:      Optional[int]   = None
    parking:        Optional[int]   = None
    erf_size:       Optional[str]   = None
    agent:          Optional[str]   = None
    url:            str
    source_page:    Optional[str]   = None
    scraped_at:     datetime

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v):
        if v is None:
            return None
        cleaned = re.sub(r"[^\d]", "", str(v))
        return int(cleaned) if cleaned else None

    @field_validator("bedrooms", "bathrooms", "parking", mode="before")
    @classmethod
    def parse_int(cls, v):
        if v is None:
            return None
        cleaned = re.sub(r"[^\d]", "", str(v))
        return int(cleaned) if cleaned else None


# =====================
# LISTING ID STRATEGY
# =====================
def build_listing_id(link: str, title: str, price_value: str, location: str) -> str:
    """
    Priority:
    1. Extract from URL pattern /XX000000
    2. Hash fallback from title + price + location
    """
    match = re.search(r'/([A-Z]{2}\d+)$', link)
    if match:
        return f"PP_{match.group(1)}"

    raw = f"{title}_{price_value}_{location}"
    return f"PP_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


# =====================
# HELPERS
# =====================
def get_soup(url: str, retries: int = 3) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                logger.warning(f"Failed after {retries} retries: {url} — {e}")
                raise


def extract_price(price_div) -> tuple[Optional[str], Optional[str]]:
    if not price_div:
        return None, None
    raw       = price_div.get_text(" ", strip=True)
    price_raw = raw.replace("per month", "").strip()
    value     = re.sub(r"[^\d]", "", price_raw)
    return price_raw, value or None


def get_max_pages() -> int:
    url        = BASE_URL_TEMPLATE.format(page_suffix="")
    soup       = get_soup(url)
    page_links = soup.select("ul.paging__pages li a.paging__btn--number")
    if page_links:
        try:
            return int(page_links[-1].get_text(strip=True))
        except ValueError:
            pass
    return 1


# =====================
# DETAIL PAGE
# =====================
def scrape_detail_page(url: str) -> dict:
    data = {}
    try:
        time.sleep(0.3)
        soup = get_soup(url)
        for li in soup.select("div.property-details li.property-details__list-item"):
            label_span = li.select_one("span.property-details__name-value")
            if not label_span:
                continue
            label      = label_span.contents[0].strip()
            value_span = li.select_one("span.property-details__value")
            value      = value_span.get_text(strip=True) if value_span else None
            if "Listing number" in label:
                data["listing_number"] = value
            elif "Property type" in label:
                data["property_type"]  = value
            elif "Listing date" in label:
                data["listing_date"]   = value
            elif "Land size" in label:
                data["erf_size"]       = value
    except Exception as e:
        logger.warning(f"Detail page failed {url}: {e}")
    return data


# =====================
# LISTING PAGE SCRAPER
# =====================
def scrape_listings(soup: BeautifulSoup, source_url: str) -> list[dict]:
    listings = []
    cards    = soup.select("a.listing-result, a.featured-listing")

    for card in cards:
        data = {"source_page": source_url}

        link        = urljoin("https://www.privateproperty.co.za", card.get("href", ""))
        data["url"] = link

        title_div = (
            card.select_one("div.listing-result__title")
            or card.select_one("div.featured-listing__title")
        )
        data["title"] = title_div.get_text(" ", strip=True) if title_div else None

        price_div = (
            card.select_one("div.listing-result__price")
            or card.select_one("div.featured-listing__price")
        )
        price_raw, price_value = extract_price(price_div)
        data["price_raw"] = price_raw
        data["price"]     = price_value

        address_span   = card.select_one("span.listing-result__address")
        data["address"] = address_span.get_text(" ", strip=True) if address_span else None

        suburb_span   = card.select_one("span.listing-result__desktop-suburb")
        data["suburb"] = suburb_span.get_text(strip=True) if suburb_span else None

        # Geo from embedded JSON-LD
        json_ld = card.find("script", type="application/ld+json")
        if json_ld:
            try:
                ld  = json.loads(json_ld.string)
                geo = ld.get("geo", {})
                data["latitude"]  = geo.get("latitude")
                data["longitude"] = geo.get("longitude")
                if data.get("latitude") and data.get("longitude"):
                    data["geo_source"] = "direct"
            except Exception:
                pass

        features = card.select(
            "span.listing-result__feature, span.featured-listing__feature"
        )
        for feature in features:
            title_attr = feature.get("title")
            val        = feature.get_text(strip=True)
            if title_attr == "Bedrooms":
                data["bedrooms"] = val
            elif title_attr == "Bathrooms":
                data["bathrooms"] = val
            elif title_attr == "Parking spaces":
                data["parking"]  = val
            elif title_attr == "Land size":
                data["erf_size"] = val

        agent         = card.select_one(".featured-listing__agent-name")
        data["agent"] = agent.get_text(strip=True) if agent else None

        data["listing_id"] = build_listing_id(
            link,
            data.get("title")  or "",
            data.get("price")  or "",
            data.get("suburb") or "",
        )

        listings.append(data)

    return listings


# =====================
# S3 UPLOAD
# =====================
def upload_to_s3(df: pd.DataFrame, scraped_at: datetime) -> str:
    """Serialise DataFrame to Parquet and upload to S3. Returns the S3 key."""
    s = get_settings()
    key = (
        f"privateproperty/"
        f"year={scraped_at.year}/"
        f"month={scraped_at.month:02d}/"
        f"day={scraped_at.day:02d}/"
        f"listings_{scraped_at.strftime('%Y%m%d_%H%M%S')}.parquet"
    )

    buffer = BytesIO()
    df.to_parquet(buffer, index=False, compression="snappy")
    buffer.seek(0)

    s3 = boto3.client(
        "s3",
        aws_access_key_id     = s.aws_access_key_id,
        aws_secret_access_key = s.aws_secret_access_key,
        region_name           = s.aws_region,
    )
    s3.upload_fileobj(buffer, s.s3_bucket_name, key)
    logger.info(f"Uploaded to s3://{s.s3_bucket_name}/{key}")
    return key


# =====================
# VALIDATE LISTINGS
# =====================
def validate_listings(raw: list[dict], scraped_at: datetime) -> list[Listing]:
    valid, failed = [], 0
    for item in raw:
        item["scraped_at"] = scraped_at
        try:
            valid.append(Listing(**item))
        except Exception as e:
            failed += 1
            logger.warning(f"Validation failed for {item.get('url')}: {e}")
    logger.info(f"Validated {len(valid)} listings / {failed} failed")
    return valid


# =====================
# MAIN RUN
# =====================
def run(upload: bool = True) -> tuple[pd.DataFrame, str | None]:
    """
    Scrape Private Property, validate, and upload to S3.
    Returns (DataFrame, s3_key). s3_key is None when upload=False.
    """
    s          = get_settings()
    scraped_at = datetime.now(timezone.utc)
    num_pages  = get_max_pages()
    logger.info(f"Detected {num_pages} pages to scrape")

    raw_listings: list[dict] = []

    # Step 1: listing pages
    for page in range(1, num_pages + 1):
        page_suffix = "" if page == 1 else f"&page={page}"
        url         = BASE_URL_TEMPLATE.format(page_suffix=page_suffix)
        logger.info(f"Scraping page {page}/{num_pages}")
        soup = get_soup(url)
        raw_listings.extend(scrape_listings(soup, url))
        time.sleep(DELAY_SECONDS)

    logger.info(f"Found {len(raw_listings)} listings — fetching detail pages...")

    # Step 2: detail pages in batches
    for i in range(0, len(raw_listings), BATCH_SIZE):
        batch = raw_listings[i : i + BATCH_SIZE]
        logger.info(f"Detail batch {i} → {i + len(batch)}")
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {
                executor.submit(scrape_detail_page, listing["url"]): idx
                for idx, listing in enumerate(batch, start=i)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    raw_listings[idx].update(future.result())
                except Exception:
                    pass

    # Step 3: validate
    listings = validate_listings(raw_listings, scraped_at)

    # Step 4: to DataFrame
    df = pd.DataFrame([l.model_dump() for l in listings])

    # Step 5: upload or local save
    s3_key = None
    if upload:
        s3_key = upload_to_s3(df, scraped_at)
    else:
        out = s.local_output_dir / "privateproperty_listings.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        logger.info(f"Saved locally to {out}")

    logger.info(f"Scrape complete — {len(df)} records")
    return df, s3_key


# =====================
# ENTRY POINT
# =====================
if __name__ == "__main__":
    run(upload=False)