"""
PCPartPicker Scraper — Storage, PSU, CPU Cooler
Outputs: storage_data.csv, psu_data.csv, cooler_data.csv

Prices are in USD and auto-converted to INR.
Update USD_TO_INR below if the rate has changed.

Usage:
    python scraper_pcpp.py              # all 3
    python scraper_pcpp.py storage
    python scraper_pcpp.py psu
    python scraper_pcpp.py cooler

Requirements:
    pip install requests beautifulsoup4 pandas
"""

import sys
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ── Update this if needed ─────────────────────────────────────
USD_TO_INR = 84.0

DELAY     = 2.0
MAX_PAGES = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://pcpartpicker.com/",
}

BASE_URL = "https://pcpartpicker.com"

CATEGORIES = {
    "storage": {
        "url":    "/products/internal-hard-drive/",
        "output": "storage_data.csv",
    },
    "psu": {
        "url":    "/products/power-supply/",
        "output": "psu_data.csv",
    },
    "cooler": {
        "url":    "/products/cpu-cooler/",
        "output": "cooler_data.csv",
    },
}


# ─────────────────────────────────────────────────────────────
# CORE
# ─────────────────────────────────────────────────────────────

def get_page(url: str, retries=3) -> BeautifulSoup | None:
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=20)
            print(f"HTTP {resp.status_code}", end=" ")
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"— rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"— failed")
                return None
        except Exception as e:
            print(f"— error: {e}")
        time.sleep(DELAY * (attempt + 1))
    return None


def extract_price_usd(text: str) -> float:
    text = str(text).replace("$", "").replace(",", "").strip()
    m = re.search(r"\d+\.?\d*", text)
    return float(m.group()) if m else 0.0


def usd_to_inr(usd: float) -> int:
    return int(usd * USD_TO_INR)


def extract_products(soup: BeautifulSoup) -> list[dict]:
    """
    PCPartPicker product listing:
    Each row is a <tr> inside table.xs-col-12
    Name:  td.td__name > p > a.primary_link  (or just a[href*="/product/"])
    Price: td.td__price > a  (or span.price__number)
    """
    products = []

    rows = soup.select("tr.tr__product")
    if not rows:
        # fallback
        rows = soup.select("tbody tr")

    for row in rows:
        try:
            # Name
            name_tag = (
                row.select_one("td.td__name p a.primary_link") or
                row.select_one("td.td__name a") or
                row.select_one("p.title a")
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            # Price
            price_tag = (
                row.select_one("td.td__price a")   or
                row.select_one("td.td__price span") or
                row.select_one("span.price__number")
            )
            if not price_tag:
                continue

            price_usd = extract_price_usd(price_tag.get_text(strip=True))
            if price_usd <= 0:
                continue

            price_inr = usd_to_inr(price_usd)
            products.append({"Name": name, "Price": price_inr})

        except Exception:
            continue

    return products


def get_next_page_url(soup: BeautifulSoup) -> str | None:
    """PCPartPicker uses ?page=N pagination."""
    next_btn = soup.select_one("a[rel='next']") or soup.select_one("li.next a")
    if next_btn:
        href = next_btn.get("href", "")
        return BASE_URL + href if href.startswith("/") else href
    return None


def scrape(category: str) -> list[dict]:
    cfg = CATEGORIES[category]
    url = BASE_URL + cfg["url"]
    all_products = []

    print(f"\n  URL: {url}")

    page = 1
    while page <= MAX_PAGES:
        print(f"    Page {page}... ", end="", flush=True)

        soup = get_page(url)
        if not soup:
            break

        products = extract_products(soup)
        if not products:
            print("no products — stopping")
            break

        all_products.extend(products)
        print(f"— {len(products)} products")

        next_url = get_next_page_url(soup)
        if not next_url:
            break

        url  = next_url
        page += 1
        time.sleep(DELAY)

    return all_products


# ─────────────────────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────────────────────

def enrich_storage(df: pd.DataFrame) -> pd.DataFrame:
    def get_type(name):
        n = name.lower()
        if any(x in n for x in ["nvme", "m.2", "pcie", "gen 4", "gen4", "gen 5"]):
            return "NVMe"
        elif "ssd" in n:
            return "SATA SSD"
        return "HDD"

    def get_capacity(name):
        n = name.upper()
        m = re.search(r"(\d+\.?\d*)\s*TB", n)
        if m: return f"{m.group(1)}TB"
        m = re.search(r"(\d+)\s*GB", n)
        if m: return f"{m.group(1)}GB"
        return ""

    df["Type"]     = df["Name"].apply(get_type)
    df["Capacity"] = df["Name"].apply(get_capacity)
    return df


def enrich_psu(df: pd.DataFrame) -> pd.DataFrame:
    def get_wattage(name):
        m = re.search(r"(\d{3,4})\s*[Ww]", name)
        return int(m.group(1)) if m else ""

    def get_efficiency(name):
        n = name.lower()
        for tier in ["titanium", "platinum", "gold", "silver", "bronze"]:
            if tier in n: return tier.capitalize()
        return "Bronze"

    df["Wattage"]    = df["Name"].apply(get_wattage)
    df["Efficiency"] = df["Name"].apply(get_efficiency)
    return df


def enrich_cooler(df: pd.DataFrame) -> pd.DataFrame:
    def get_type(name):
        n = name.lower()
        return "AIO" if any(x in n for x in ["aio", "liquid", "240mm", "280mm", "360mm"]) else "Air"

    def get_tdp(name):
        m = re.search(r"(\d{2,3})\s*[Ww]\s*(tdp)?", name, re.IGNORECASE)
        if m: return int(m.group(1))
        n = name.lower()
        if "360" in n: return 300
        if "280" in n: return 250
        if "240" in n: return 200
        if any(x in n for x in ["noctua", "nh-d15", "dark rock pro", "ak620"]): return 250
        if any(x in n for x in ["nh-u12", "ak400", "hyper 212"]): return 180
        return 150

    df["Type"]       = df["Name"].apply(get_type)
    df["TDP_Rating"] = df["Name"].apply(get_tdp)
    return df


ENRICHERS = {
    "storage": enrich_storage,
    "psu":     enrich_psu,
    "cooler":  enrich_cooler,
}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run(target: str):
    print(f"\n{'='*50}")
    print(f"  {target.upper()} — PCPartPicker (USD × {USD_TO_INR} = INR)")
    print(f"{'='*50}")

    products = scrape(target)

    if not products:
        print(f"\n❌  Nothing scraped for {target}.")
        return

    df  = pd.DataFrame(products).drop_duplicates(subset=["Name"]).reset_index(drop=True)
    df  = ENRICHERS[target](df)
    out = CATEGORIES[target]["output"]
    df.to_csv(out, index=False)

    print(f"\n✔  {len(df)} products saved → {out}")
    print(df.head(5).to_string())


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(CATEGORIES.keys())
    valid   = [t for t in targets if t in CATEGORIES]
    if not valid:
        print(f"Unknown target. Choose from: {list(CATEGORIES.keys())}")
        sys.exit(1)
    for t in valid:
        run(t)
    print(f"\n✅  Done! Move the CSVs into data_files/")
    print(f"    Note: prices are USD converted to INR at ₹{USD_TO_INR}/USD.")
    print(f"    Update USD_TO_INR at the top of the file to change the rate.")


if __name__ == "__main__":
    main()
