"""Unit tests for scrapers/privateproperty.py"""

import pytest
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from scrapers.privateproperty import (
    build_listing_id,
    extract_price,
    validate_listings,
    scrape_listings,
    Listing,
)


class TestBuildListingId:
    def test_extracts_id_from_url_pattern(self):
        url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/claremont/RR123456"
        assert build_listing_id(url, "Title", "15500", "Claremont") == "PP_RR123456"

    def test_falls_back_to_hash_when_no_url_id(self):
        url = "https://www.privateproperty.co.za/to-rent/western-cape/"
        result = build_listing_id(url, "Nice flat", "10000", "Gardens")
        assert result.startswith("PP_")
        assert len(result) == 15

    def test_hash_fallback_is_deterministic(self):
        url = "https://www.privateproperty.co.za/no-id"
        r1 = build_listing_id(url, "Title", "10000", "Obs")
        r2 = build_listing_id(url, "Title", "10000", "Obs")
        assert r1 == r2

    def test_different_inputs_produce_different_hashes(self):
        url = "https://www.privateproperty.co.za/no-id"
        r1 = build_listing_id(url, "Title A", "10000", "Obs")
        r2 = build_listing_id(url, "Title B", "10000", "Obs")
        assert r1 != r2

    def test_always_prefixed_pp(self):
        url = "https://www.privateproperty.co.za/to-rent/RR000001"
        assert build_listing_id(url, "", "", "").startswith("PP_")


class TestExtractPrice:
    def _make_div(self, html):
        return BeautifulSoup(html, "html.parser").find("div")

    def test_extracts_price_and_value(self):
        div = self._make_div('<div class="listing-result__price">R 15 500<span>per month</span></div>')
        price_raw, value = extract_price(div)
        assert value == "15500"

    def test_returns_none_for_none_input(self):
        raw, val = extract_price(None)
        assert raw is None
        assert val is None

    def test_strips_non_numeric_chars(self):
        div = self._make_div('<div>R 9,800 per month</div>')
        _, value = extract_price(div)
        assert value == "9800"


class TestListingModel:
    BASE = {
        "listing_id": "PP_RR123456",
        "url":        "https://www.privateproperty.co.za/to-rent/RR123456",
        "scraped_at": datetime.now(timezone.utc),
    }

    def test_valid_listing_passes(self):
        listing = Listing(**self.BASE, price="15500", bedrooms="2")
        assert listing.price == 15500
        assert listing.bedrooms == 2

    def test_price_string_with_symbols_is_cleaned(self):
        listing = Listing(**self.BASE, price="R 15 500")
        assert listing.price == 15500

    def test_platform_defaults_to_privateproperty(self):
        listing = Listing(**self.BASE)
        assert listing.platform == "privateproperty"

    def test_missing_listing_id_raises(self):
        with pytest.raises(Exception):
            Listing(url="https://example.com", scraped_at=datetime.now(timezone.utc))


class TestValidateListings:
    def test_valid_listings_pass_through(self, sample_raw_listings):
        result = validate_listings(sample_raw_listings, datetime.now(timezone.utc))
        assert len(result) == len(sample_raw_listings)

    def test_invalid_listing_is_skipped(self):
        bad = [{"url": "https://example.com"}]
        result = validate_listings(bad, datetime.now(timezone.utc))
        assert result == []

    def test_mix_of_valid_and_invalid(self, sample_raw_listings):
        bad = {"url": "https://example.com"}
        result = validate_listings(sample_raw_listings + [bad], datetime.now(timezone.utc))
        assert len(result) == len(sample_raw_listings)


LISTING_CARD_HTML = """
<a class="listing-result" href="/to-rent/western-cape/cape-town/claremont/RR999999">
  <div class="listing-result__title">Spacious 2 Bed in Claremont</div>
  <div class="listing-result__price">R 18 000<span>per month</span></div>
  <span class="listing-result__address">5 Main Road, Claremont</span>
  <span class="listing-result__desktop-suburb">Claremont</span>
  <span class="listing-result__feature" title="Bedrooms">2</span>
  <span class="listing-result__feature" title="Bathrooms">1</span>
  <span class="listing-result__feature" title="Parking spaces">1</span>
</a>
"""

class TestScrapeListings:
    def test_extracts_title(self):
        soup = BeautifulSoup(LISTING_CARD_HTML, "html.parser")
        listings = scrape_listings(soup, "https://example.com")
        assert len(listings) == 1
        assert "Claremont" in listings[0]["title"]

    def test_extracts_price(self):
        soup = BeautifulSoup(LISTING_CARD_HTML, "html.parser")
        listings = scrape_listings(soup, "https://example.com")
        assert listings[0]["price"] == "18000"

    def test_extracts_suburb(self):
        soup = BeautifulSoup(LISTING_CARD_HTML, "html.parser")
        listings = scrape_listings(soup, "https://example.com")
        assert listings[0]["suburb"] == "Claremont"

    def test_listing_id_extracted_from_url(self):
        soup = BeautifulSoup(LISTING_CARD_HTML, "html.parser")
        listings = scrape_listings(soup, "https://example.com")
        assert listings[0]["listing_id"] == "PP_RR999999"

    def test_empty_page_returns_empty_list(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert scrape_listings(soup, "https://example.com") == []
