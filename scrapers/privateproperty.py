import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
from urllib.parse import urljoin
from pathlib import Path

print("PrivateProperty scraper started")

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

NUM_PAGES = 133
DELAY_SECONDS = 2

OUTPUT_DIR = Path("data/raw/privateproperty")
OUTPUT_FILE = OUTPUT_DIR / "privateproperty_listings.csv"


# =====================
# HELPERS
# =====================
def get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def extract_price(price_div):
    if not price_div:
        return None, None, None

    raw = price_div.get_text(" ", strip=True)
    price = raw.replace("per month", "").strip()
    value = re.sub(r"[^\d]", "", price)

    return price, value, "ZAR"


# =====================
# SCRAPER
# =====================
def scrape_listings(soup: BeautifulSoup, source_url: str) -> list[dict]:
    listings = []

    # BOTH normal + featured listings
    cards = soup.select("a.listing-result, a.featured-listing")

    for card in cards:
        data = {"SourcePage": source_url}

        # -----------------
        # Link + Property_ID
        # -----------------
        link = urljoin(
            "https://www.privateproperty.co.za",
            card.get("href", "")
        )
        data["Link"] = link

        match = re.search(r'/([A-Z]{2}\d+)$', link)
        if match:
            data["Property_ID"] = match.group(1)

        # -----------------
        # Listing_ID
        # -----------------
        wishlist = card.select_one("[data-listing-id]")
        if wishlist:
            data["Listing_ID"] = wishlist.get("data-listing-id")

        # -----------------
        # JSON-LD (Geo)
        # -----------------
        json_ld = card.find("script", type="application/ld+json")
        if json_ld:
            try:
                ld = json.loads(json_ld.string)
                geo = ld.get("geo", {})
                data["Latitude"] = geo.get("latitude")
                data["Longitude"] = geo.get("longitude")
            except:
                pass

        # -----------------
        # Title
        # -----------------
        title_div = (
            card.select_one("div.listing-result__title") or
            card.select_one("div.featured-listing__title")
        )
        if title_div:
            data["Title"] = title_div.get_text(" ", strip=True)

        # -----------------
        # Price
        # -----------------
        price_div = (
            card.select_one("div.listing-result__price") or
            card.select_one("div.featured-listing__price")
        )
        price, value, currency = extract_price(price_div)
        data["Price"] = price
        data["Price_value"] = value
        data["PriceCurrency"] = currency

        # -----------------
        # Location / Address
        # -----------------
        address_span = card.select_one("span.listing-result__address")
        if address_span:
            data["Address"] = address_span.get_text(" ", strip=True)

        suburb_span = card.select_one(
            "span.listing-result__desktop-suburb"
        )
        if suburb_span:
            data["Location"] = suburb_span.get_text(strip=True)

        # -----------------
        # Features
        # -----------------
        features = card.select(
            "span.listing-result__feature, span.featured-listing__feature"
        )

        for feature in features:
            title = feature.get("title")
            value = feature.get_text(strip=True)

            if title == "Bedrooms":
                data["Bedrooms"] = value
            elif title == "Bathrooms":
                data["Bathrooms"] = value
            elif title == "Parking spaces":
                data["Parking Spaces"] = value
            elif title == "Land size":
                data["ErfSize"] = value

        # -----------------
        # Agent
        # -----------------
        agent = card.select_one(".featured-listing__agent-name")
        if agent:
            data["Agent"] = agent.get_text(strip=True)

        listings.append(data)

    return listings


# =====================
# MAIN
# =====================
def run(save: bool = True) -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_data = []

    for page in range(1, NUM_PAGES + 1):
        page_suffix = "" if page == 1 else f"&page={page}"
        url = BASE_URL_TEMPLATE.format(page_suffix=page_suffix)

        print(f"Scraping page {page}/{NUM_PAGES}")
        soup = get_soup(url)
        listings = scrape_listings(soup, url)
        all_data.extend(listings)

        time.sleep(DELAY_SECONDS)

    df = pd.DataFrame(all_data)
    df["ScrapeDate"] = pd.Timestamp.now()

    preferred_order = [
        "Property_ID", "Listing_ID",
        "Title", "Price", "Price_value", "PriceCurrency",
        "Location", "Address",
        "Bedrooms", "Bathrooms", "Parking Spaces", "ErfSize",
        "Latitude", "Longitude",
        "Agent",
        "Link", "SourcePage", "ScrapeDate"
    ]

    df = df[
        [c for c in preferred_order if c in df.columns]
        + [c for c in df.columns if c not in preferred_order]
    ]

    if save:
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"Saved {len(df)} records to {OUTPUT_FILE}")

    return df


# =====================
# ENTRY POINT
# =====================
if __name__ == "__main__":
    run()