"""
PC Parts Scraper — MDComputers + Vedant Computers fallback
Scrapes: Storage, PSU, CPU Cooler

Usage:
    python scraper_fixed.py              # tries MDComputers first, falls back to Vedant
    python scraper_fixed.py storage
    python scraper_fixed.py psu
    python scraper_fixed.py cooler

Requirements:
    pip install requests beautifulsoup4 pandas
"""

import time
import sys
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

DELAY     = 2.0
MAX_PAGES = 10

# ─────────────────────────────────────────────────────────────
# SESSION SETUP — mimics a real Chrome browser visit
# ─────────────────────────────────────────────────────────────

def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    return session


def get_page(session, url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=20)
            print(f"HTTP {resp.status_code}", end=" ")
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            elif resp.status_code == 403:
                print("— blocked")
                return None
            elif resp.status_code == 404:
                print("— not found")
                return None
        except Exception as e:
            print(f"— error: {e}")
        time.sleep(DELAY * (attempt + 1))
    return None


def extract_price(text):
    text = str(text).replace("₹", "").replace(",", "").strip()
    m = re.search(r"\d+\.?\d*", text)
    return float(m.group()) if m else 0.0


# ─────────────────────────────────────────────────────────────
# MDCOMPUTERS
# ─────────────────────────────────────────────────────────────

MD_BASE = "https://www.mdcomputers.in"

MD_CATEGORIES = {
    "storage": ["/storage-ssd-internal", "/internal-hard-disk-drive"],
    "psu":     ["/power-supply-unit"],
    "cooler":  ["/cpu-air-cooler", "/cpu-liquid-cooler"],
}

MD_OUTPUTS = {
    "storage": "storage_data.csv",
    "psu":     "psu_data.csv",
    "cooler":  "cooler_data.csv",
}


def md_extract_products(soup):
    products = []
    # MDComputers uses OpenCart — product cards are in div.product-layout
    for item in soup.select("div.product-layout, div.product-thumb"):
        try:
            name_tag = item.select_one("h4 a") or item.select_one("div.caption h4 a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            price_tag = (
                item.select_one("span.price-normal") or
                item.select_one("span.price-new") or
                item.select_one("p.price") or
                item.select_one("div.price")
            )
            if not price_tag:
                continue

            price = extract_price(price_tag.get_text(strip=True))
            if price > 0:
                products.append({"Name": name, "Price": price})
        except Exception:
            continue
    return products


def md_has_next(soup):
    pg = soup.select_one("ul.pagination")
    if not pg:
        return False
    return any(">" in a.get_text() or "next" in a.get("class", []) for a in pg.select("a"))


def scrape_mdcomputers(target):
    session = make_session()
    # Visit homepage first to get cookies
    print("  Visiting MDComputers homepage for cookies...")
    session.get(MD_BASE, timeout=15)
    time.sleep(1.5)

    all_products = []
    for path in MD_CATEGORIES[target]:
        print(f"\n  Category: {MD_BASE}{path}")
        for page in range(1, MAX_PAGES + 1):
            url = f"{MD_BASE}{path}?page={page}" if page > 1 else f"{MD_BASE}{path}"
            print(f"    Page {page}... ", end="", flush=True)

            soup = get_page(session, url)
            if not soup:
                break

            products = md_extract_products(soup)
            if not products:
                print("no products")
                break

            all_products.extend(products)
            print(f"— {len(products)} products")

            if not md_has_next(soup):
                break
            time.sleep(DELAY)

    return all_products


# ─────────────────────────────────────────────────────────────
# VEDANT COMPUTERS  (corrected URLs)
# ─────────────────────────────────────────────────────────────

VD_BASE = "https://www.vedantcomputers.com"

VD_CATEGORIES = {
    "storage": [
        "/product-category/storage/ssd",
        "/product-category/storage/internal-hard-drive",
        "/product-category/storage",
    ],
    "psu": [
        "/product-category/power-supply",
        "/product-category/psu",
    ],
    "cooler": [
        "/product-category/cooling/air-cooler",
        "/product-category/cooling/liquid-cooler",
        "/product-category/cooling",
    ],
}


def vd_extract_products(soup):
    products = []
    # WooCommerce layout
    for item in soup.select("li.product, div.product-grid-item, article.product"):
        try:
            name_tag = (
                item.select_one("h2.woocommerce-loop-product__title") or
                item.select_one("h3.product-title") or
                item.select_one("h2") or
                item.select_one("h3")
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            # WooCommerce price — prefer sale price (ins) over regular
            price_tag = (
                item.select_one("ins .woocommerce-Price-amount") or
                item.select_one("ins bdi") or
                item.select_one("span.woocommerce-Price-amount") or
                item.select_one("bdi")
            )
            if not price_tag:
                continue

            price = extract_price(price_tag.get_text(strip=True))
            if price > 0:
                products.append({"Name": name, "Price": price})
        except Exception:
            continue
    return products


def vd_has_next(soup):
    nav = soup.select_one("nav.woocommerce-pagination, a.next")
    return nav is not None


def scrape_vedant(target):
    session = make_session()
    print("  Visiting Vedant homepage for cookies...")
    session.get(VD_BASE, timeout=15)
    time.sleep(1.5)

    all_products = []
    paths = VD_CATEGORIES[target]

    for path in paths:
        print(f"\n  Category: {VD_BASE}{path}")
        for page in range(1, MAX_PAGES + 1):
            url = f"{VD_BASE}{path}/page/{page}/" if page > 1 else f"{VD_BASE}{path}/"
            print(f"    Page {page}... ", end="", flush=True)

            soup = get_page(session, url)
            if not soup:
                break

            products = vd_extract_products(soup)
            if not products:
                print("no products")
                break

            all_products.extend(products)
            print(f"— {len(products)} products")

            if not vd_has_next(soup):
                break
            time.sleep(DELAY)

        if all_products:
            break  # stop trying other paths once we find working one

    return all_products


# ─────────────────────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────────────────────

def enrich_storage(df):
    def get_type(name):
        n = name.lower()
        if any(x in n for x in ["nvme", "m.2", "pcie", "gen 4", "gen4", "gen 5", "gen5"]):
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


def enrich_psu(df):
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


def enrich_cooler(df):
    def get_type(name):
        n = name.lower()
        return "AIO" if any(x in n for x in ["aio", "liquid", "240", "280", "360", "120mm liquid"]) else "Air"

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


ENRICHERS = {"storage": enrich_storage, "psu": enrich_psu, "cooler": enrich_cooler}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run(target):
    print(f"\n{'='*50}")
    print(f"  {target.upper()}")
    print(f"{'='*50}")

    # Try MDComputers first
    print("\n  Trying MDComputers...")
    products = scrape_mdcomputers(target)

    # Fall back to Vedant
    if not products:
        print(f"\n  MDComputers blocked/failed — trying Vedant Computers...")
        products = scrape_vedant(target)

    if not products:
        print(f"\n❌  Both sources failed for {target}.")
        print("    Try running with --primeabgb flag or manually inspect the site HTML.")
        return

    df = pd.DataFrame(products).drop_duplicates(subset=["Name"]).reset_index(drop=True)
    df = ENRICHERS[target](df)

    out = MD_OUTPUTS[target]
    df.to_csv(out, index=False)
    print(f"\n✔  {len(df)} products saved → {out}")
    print(df.head(3).to_string())


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["storage", "psu", "cooler"]
    for t in targets:
        run(t.lower())
    print("\n✅  Done! Move the CSVs into pc_builder_final/data_files/")


if __name__ == "__main__":
    main()
