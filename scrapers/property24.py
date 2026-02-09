import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
from pathlib import Path

print("Script Started")
# =====================
# CONFIG
# =====================
BASE_URL_TEMPLATE = (
    "https://www.property24.com/to-rent/cape-town/western-cape/432{page_suffix}"
    "?PropertyCategory=House%2cApartmentOrFlat%2cTownhouse"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

NUM_PAGES = 97
DELAY_SECONDS = 2

# project-root-relative path
OUTPUT_DIR = Path("data/raw/property24")
OUTPUT_FILE = OUTPUT_DIR / "property24_listings.csv"


# =====================
# SCRAPING FUNCTIONS
# =====================
def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def scrape_listings(soup: BeautifulSoup, source_url: str) -> list[dict]:
    listings = []

    for card in soup.find_all("a", class_="p24_content"):
        data = {"SourcePage": source_url}
        data["Link"] = urljoin("https://www.property24.com", card.get("href", ""))

        for span in card.find_all("span", class_=lambda x: x and x.startswith("p24_")):
            class_name = span["class"][0]
            field_name = class_name.replace("p24_", "").capitalize()
            data[field_name] = span.get_text(strip=True)

            if "p24_price" in class_name:
                if span.has_attr("content"):
                    data["Price_value"] = span["content"]

                currency_tag = span.find("meta", attrs={"itemprop": "priceCurrency"})
                if currency_tag and currency_tag.get("content"):
                    data["PriceCurrency"] = currency_tag["content"]

        for fs in card.find_all("span", class_="p24_featureDetails"):
            title = fs.get("title", "").strip()
            value = fs.find("span")
            if title:
                data[title] = value.get_text(strip=True) if value else None

        size_span = card.find("span", class_="p24_size")
        if size_span:
            data["ErfSize"] = (
                size_span.get_text(strip=True)
                .replace("Erf Size", "")
                .strip()
            )

        listings.append(data)

    return listings


# =====================
# MAIN RUN FUNCTION
# =====================
def run() -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_data = []

    for page_num in range(1, NUM_PAGES + 1):
        page_suffix = "" if page_num == 1 else f"/p{page_num}"
        url = BASE_URL_TEMPLATE.format(page_suffix=page_suffix)

        print(f"Scraping page {page_num}/{NUM_PAGES}")
        soup = get_soup(url)
        listings = scrape_listings(soup, url)
        all_data.extend(listings)

        time.sleep(DELAY_SECONDS)

    df = pd.DataFrame(all_data)
    df["ScrapeDate"] = pd.Timestamp.now()

    preferred_order = [
        "Title", "Price", "Price_value", "PriceCurrency",
        "Location", "Address", "Bedrooms", "Bathrooms",
        "Parking Spaces", "ErfSize", "Link", "SourcePage", "ScrapeDate"
    ]

    df = df[
        [c for c in preferred_order if c in df.columns]
        + [c for c in df.columns if c not in preferred_order]
    ]

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} records to {OUTPUT_FILE}")

    return df


# =====================
# ENTRY POINT
# =====================
if __name__ == "__main__":
    run()
