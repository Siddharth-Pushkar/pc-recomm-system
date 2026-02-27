"""
Vedant Computers Scraper — fallback if MDComputers doesn't work
Targets: Storage, PSU, CPU Cooler

Usage:
    python scraper_vedant.py              # all 3
    python scraper_vedant.py storage
    python scraper_vedant.py psu
    python scraper_vedant.py cooler

Requirements:
    pip install requests beautifulsoup4 pandas
"""

import time
import sys
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

DELAY    = 1.5
MAX_PAGES = 10
BASE_URL  = "https://www.vedantcomputers.com"

CATEGORIES = {
    "storage": {
        "urls": [
            "/internal-ssd",
            "/internal-hard-disk",
        ],
        "output": "storage_data.csv",
    },
    "psu": {
        "urls": [
            "/smps-power-supply",
        ],
        "output": "psu_data.csv",
    },
    "cooler": {
        "urls": [
            "/cpu-cooler",
            "/liquid-cooler",
        ],
        "output": "cooler_data.csv",
    },
}


def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "html.parser")
            print(f"  ⚠  HTTP {r.status_code}")
        except Exception as e:
            print(f"  ⚠  Error: {e}")
        time.sleep(DELAY * (attempt + 1))
    return None


def extract_price(text):
    text = str(text).replace("₹", "").replace(",", "").strip()
    m = re.search(r"\d+\.?\d*", text)
    return float(m.group()) if m else 0.0


def extract_products(soup):
    products = []

    # Vedant uses WooCommerce-style layout
    items = (
        soup.select("li.product") or
        soup.select("div.product-grid-item") or
        soup.select("div.product-item") or
        soup.select("div.woocommerce-product")
    )

    for item in items:
        try:
            name_tag = (
                item.select_one("h2.woocommerce-loop-product__title") or
                item.select_one("h3") or
                item.select_one("a.product-title") or
                item.select_one("span.product-title")
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            price_tag = (
                item.select_one("span.woocommerce-Price-amount") or
                item.select_one("span.price") or
                item.select_one("ins span.amount") or
                item.select_one("span.amount")
            )
            if not price_tag:
                continue

            price = extract_price(price_tag.get_text(strip=True))
            if price <= 0:
                continue

            products.append({"Name": name, "Price": price})
        except Exception:
            continue

    return products


def has_next_page(soup, page):
    nav = soup.select_one("nav.woocommerce-pagination") or soup.select_one("ul.page-numbers")
    if not nav:
        return False
    return any("next" in a.get("class", []) or "»" in a.get_text() for a in nav.select("a"))


def scrape_category(urls):
    all_products = []
    for path in urls:
        print(f"\n  Scraping: {BASE_URL}{path}")
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}{path}/page/{page}/" if page > 1 else f"{BASE_URL}{path}/"
            print(f"    Page {page}...", end=" ", flush=True)

            soup = get_page(url)
            if not soup:
                print("failed")
                break

            products = extract_products(soup)
            if not products:
                print("no products — stopping")
                break

            all_products.extend(products)
            print(f"{len(products)} products")

            if not has_next_page(soup, page):
                break
            time.sleep(DELAY)

    return all_products


# ── Enrichment (same logic as mdcomputers scraper) ────────────────────────

def enrich_storage(df):
    def get_type(name):
        n = name.lower()
        if any(x in n for x in ["nvme", "m.2", "pcie", "gen4", "gen 4", "gen5", "gen 5"]):
            return "NVMe"
        elif "ssd" in n:
            return "SATA SSD"
        return "HDD"

    def get_capacity(name):
        n = name.upper()
        m_tb = re.search(r"(\d+\.?\d*)\s*TB", n)
        m_gb = re.search(r"(\d+)\s*GB", n)
        if m_tb: return f"{m_tb.group(1)}TB"
        if m_gb: return f"{m_gb.group(1)}GB"
        return ""

    df["Type"]     = df["Name"].apply(get_type)
    df["Capacity"] = df["Name"].apply(get_capacity)
    return df


def enrich_psu(df):
    def get_wattage(name):
        m = re.search(r"(\d{3,4})\s*[Ww]", name)
        return int(m.group(1)) if m else ""

    def get_efficiency(name):
        n = name.lower()
        for tier in ["titanium", "platinum", "gold", "silver", "bronze"]:
            if tier in n:
                return tier.capitalize()
        return "Bronze"

    df["Wattage"]    = df["Name"].apply(get_wattage)
    df["Efficiency"] = df["Name"].apply(get_efficiency)
    return df


def enrich_cooler(df):
    def get_type(name):
        n = name.lower()
        return "AIO" if any(x in n for x in ["aio", "liquid", "240", "280", "360"]) else "Air"

    def get_tdp(name):
        m = re.search(r"(\d{2,3})\s*[Ww]\s*(tdp)?", name, re.IGNORECASE)
        if m: return int(m.group(1))
        n = name.lower()
        if "360" in n: return 300
        if "280" in n: return 250
        if "240" in n: return 200
        if "120" in n: return 130
        if any(x in n for x in ["noctua", "nh-d15", "dark rock"]): return 250
        return 150

    df["Type"]       = df["Name"].apply(get_type)
    df["TDP_Rating"] = df["Name"].apply(get_tdp)
    return df


ENRICHERS = {
    "storage": enrich_storage,
    "psu":     enrich_psu,
    "cooler":  enrich_cooler,
}


def run_scraper(target):
    if target not in CATEGORIES:
        print(f"Unknown: {target}")
        return
    cfg = CATEGORIES[target]
    print(f"\n{'='*50}\n  {target.upper()} — Vedant Computers\n{'='*50}")

    products = scrape_category(cfg["urls"])
    if not products:
        print(f"❌  Nothing scraped for {target}.")
        return

    df = pd.DataFrame(products).drop_duplicates(subset=["Name"]).reset_index(drop=True)
    df = ENRICHERS[target](df)
    df.to_csv(cfg["output"], index=False)
    print(f"\n✔  {len(df)} products → {cfg['output']}")
    print(df.head(5).to_string())


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(CATEGORIES.keys())
    for t in targets:
        run_scraper(t.lower())
    print("\n✅  Done! Move CSVs into pc_builder_final/data_files/")


if __name__ == "__main__":
    main()
