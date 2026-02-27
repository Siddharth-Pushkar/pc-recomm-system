"""
MDComputers Scraper — Storage, PSU, CPU Cooler
Outputs: storage_data.csv, psu_data.csv, cooler_data.csv

Usage:
    python scraper.py              # scrapes all 3
    python scraper.py storage      # scrapes only storage
    python scraper.py psu          # scrapes only PSU
    python scraper.py cooler       # scrapes only cooler

Requirements:
    pip install requests beautifulsoup4 pandas
"""

import time
import sys
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DELAY = 1.5   # seconds between requests (be polite)
MAX_PAGES = 10

BASE_URL = "https://www.mdcomputers.in"

# Category URLs on MDComputers
CATEGORIES = {
    "storage": {
        "urls": [
            "/storage-ssd-internal",          # NVMe + SATA SSDs
            "/internal-hard-disk-drive",       # HDDs
        ],
        "output": "storage_data.csv",
    },
    "psu": {
        "urls": [
            "/power-supply-unit",
        ],
        "output": "psu_data.csv",
    },
    "cooler": {
        "urls": [
            "/cpu-air-cooler",
            "/cpu-liquid-cooler",
        ],
        "output": "cooler_data.csv",
    },
}


# ─────────────────────────────────────────────────────────────
# CORE SCRAPING
# ─────────────────────────────────────────────────────────────

def get_page(url: str, retries=3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            print(f"  ⚠  HTTP {resp.status_code} for {url}")
        except requests.RequestException as e:
            print(f"  ⚠  Request error (attempt {attempt+1}): {e}")
        time.sleep(DELAY * (attempt + 1))
    return None


def extract_products(soup: BeautifulSoup) -> list[dict]:
    """
    MDComputers product listing structure:
    Each product is in a div.product-layout > div.product-thumb
    Name: h4 > a
    Price: span.price-normal  OR  p.price > span
    """
    products = []

    # Try primary selector
    items = soup.select("div.product-layout")
    if not items:
        # Fallback
        items = soup.select("div.product-thumb")

    for item in items:
        try:
            # Name
            name_tag = item.select_one("h4 a") or item.select_one("div.caption a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            # Price — try multiple selectors
            price_tag = (
                item.select_one("span.price-normal") or
                item.select_one("p.price span") or
                item.select_one("span.price-new") or
                item.select_one("div.price")
            )
            if not price_tag:
                continue

            price_text = price_tag.get_text(strip=True)
            price = extract_price(price_text)
            if price <= 0:
                continue

            products.append({"Name": name, "Price": price})

        except Exception as e:
            continue

    return products


def has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    """Check if there's a next page in pagination."""
    pagination = soup.select_one("ul.pagination")
    if not pagination:
        return False
    links = pagination.select("a")
    for link in links:
        if ">" in link.get_text() or "Next" in link.get_text():
            return True
    return False


def scrape_category(category_urls: list[str], max_pages=MAX_PAGES) -> list[dict]:
    all_products = []

    for base_path in category_urls:
        print(f"\n  Scraping: {BASE_URL}{base_path}")

        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}{base_path}?page={page}" if page > 1 else f"{BASE_URL}{base_path}"
            print(f"    Page {page}...", end=" ", flush=True)

            soup = get_page(url)
            if not soup:
                print("failed")
                break

            products = extract_products(soup)
            if not products:
                print("no products found — stopping")
                break

            all_products.extend(products)
            print(f"{len(products)} products")

            if not has_next_page(soup, page):
                break

            time.sleep(DELAY)

    return all_products


# ─────────────────────────────────────────────────────────────
# PRICE EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_price(text: str) -> float:
    text = text.replace("₹", "").replace(",", "").strip()
    match = re.search(r"\d+\.?\d*", text)
    return float(match.group()) if match else 0.0


# ─────────────────────────────────────────────────────────────
# ENRICHMENT — add extra columns from product name
# ─────────────────────────────────────────────────────────────

def enrich_storage(df: pd.DataFrame) -> pd.DataFrame:
    """Add Type (NVMe/SATA SSD/HDD) and Capacity columns."""
    def get_type(name):
        name_l = name.lower()
        if any(x in name_l for x in ["nvme", "m.2", "pcie", "gen 4", "gen4", "gen 5", "gen5"]):
            return "NVMe"
        elif any(x in name_l for x in ["ssd", "solid state"]):
            return "SATA SSD"
        elif any(x in name_l for x in ["hdd", "hard disk", "hard drive", "seagate barracuda", "wd blue", "toshiba"]):
            return "HDD"
        return "SSD"

    def get_capacity(name):
        name_u = name.upper()
        m_tb = re.search(r"(\d+\.?\d*)\s*TB", name_u)
        m_gb = re.search(r"(\d+)\s*GB", name_u)
        if m_tb:
            return f"{m_tb.group(1)}TB"
        elif m_gb:
            return f"{m_gb.group(1)}GB"
        return ""

    df["Type"]     = df["Name"].apply(get_type)
    df["Capacity"] = df["Name"].apply(get_capacity)
    return df


def enrich_psu(df: pd.DataFrame) -> pd.DataFrame:
    """Add Wattage and Efficiency columns."""
    def get_wattage(name):
        m = re.search(r"(\d{3,4})\s*[Ww]", name)
        return int(m.group(1)) if m else ""

    def get_efficiency(name):
        name_l = name.lower()
        if "titanium" in name_l: return "Titanium"
        if "platinum" in name_l: return "Platinum"
        if "gold"     in name_l: return "Gold"
        if "silver"   in name_l: return "Silver"
        if "bronze"   in name_l: return "Bronze"
        if "white"    in name_l: return "White"
        return "Bronze"  # default assumption

    df["Wattage"]    = df["Name"].apply(get_wattage)
    df["Efficiency"] = df["Name"].apply(get_efficiency)
    return df


def enrich_cooler(df: pd.DataFrame) -> pd.DataFrame:
    """Add Type and TDP_Rating columns."""
    def get_type(name):
        name_l = name.lower()
        if any(x in name_l for x in ["aio", "liquid", "240", "280", "360", "120mm liquid"]):
            return "AIO"
        return "Air"

    def get_tdp(name):
        # Try to extract TDP from name e.g. "200W TDP" or "TDP 250W"
        m = re.search(r"(\d{2,3})\s*[Ww]\s*(tdp)?", name, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # Estimate from AIO size
        name_l = name.lower()
        if "360" in name_l: return 300
        if "280" in name_l: return 250
        if "240" in name_l: return 200
        if "120" in name_l: return 130
        # Air cooler estimation
        if any(x in name_l for x in ["noctua", "nh-d15", "be quiet dark", "ak620"]): return 250
        if any(x in name_l for x in ["nh-u12", "ak400", "hyper 212"]): return 180
        return 150  # default

    df["Type"]       = df["Name"].apply(get_type)
    df["TDP_Rating"] = df["Name"].apply(get_tdp)
    return df


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run_scraper(target: str):
    if target not in CATEGORIES:
        print(f"Unknown target '{target}'. Choose from: {list(CATEGORIES.keys())}")
        return

    cfg = CATEGORIES[target]
    print(f"\n{'='*50}")
    print(f"  Scraping: {target.upper()}")
    print(f"{'='*50}")

    products = scrape_category(cfg["urls"])

    if not products:
        print(f"\n❌  No products scraped for {target}.")
        print("    The site structure may have changed — inspect the page HTML and update selectors.")
        return

    df = pd.DataFrame(products).drop_duplicates(subset=["Name"]).reset_index(drop=True)

    # Enrich with extra columns
    if target == "storage":
        df = enrich_storage(df)
    elif target == "psu":
        df = enrich_psu(df)
    elif target == "cooler":
        df = enrich_cooler(df)

    output_path = cfg["output"]
    df.to_csv(output_path, index=False)
    print(f"\n✔  Saved {len(df)} products → {output_path}")
    print(df.head(5).to_string())


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(CATEGORIES.keys())

    for t in targets:
        run_scraper(t.lower())

    print("\n✅  Done! Move the CSV files into your pc_builder_final/data_files/ folder.")


if __name__ == "__main__":
    main()
