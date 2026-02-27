"""
Selenium Scraper — MDComputers (bypasses Cloudflare/403)
Scrapes: Storage, PSU, CPU Cooler

Requirements:
    pip install selenium pandas
    Download ChromeDriver matching your Chrome version:
    https://googlechromelabs.github.io/chrome-for-testing/

Usage:
    python scraper_selenium.py              # all 3
    python scraper_selenium.py storage
    python scraper_selenium.py psu
    python scraper_selenium.py cooler
"""

import sys
import re
import time
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

BASE_URL  = "https://www.mdcomputers.in"
DELAY     = 2.5
MAX_PAGES = 15

CATEGORIES = {
    "storage": {
        "urls":   ["/storage-ssd-internal", "/internal-hard-disk-drive"],
        "output": "storage_data.csv",
    },
    "psu": {
        "urls":   ["/power-supply-unit"],
        "output": "psu_data.csv",
    },
    "cooler": {
        "urls":   ["/cpu-air-cooler", "/cpu-liquid-cooler"],
        "output": "cooler_data.csv",
    },
}


# ─────────────────────────────────────────────────────────────
# DRIVER SETUP
# ─────────────────────────────────────────────────────────────

def make_driver():
    opts = Options()

    # Comment out the next line if you want to SEE the browser window
    opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=opts)

    # Hide webdriver flag (bypasses basic bot detection)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


# ─────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────

def get_products_from_page(driver) -> list[dict]:
    soup     = BeautifulSoup(driver.page_source, "html.parser")
    products = []

    for item in soup.select("div.product-layout, div.product-thumb"):
        try:
            name_tag = item.select_one("h4 a") or item.select_one("div.caption h4 a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            price_tag = (
                item.select_one("span.price-normal") or
                item.select_one("span.price-new")    or
                item.select_one("p.price")           or
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


def has_next_page(driver) -> bool:
    try:
        pagination = driver.find_elements(By.CSS_SELECTOR, "ul.pagination a")
        return any(">" in a.text or "next" in a.get_attribute("class").lower()
                   for a in pagination)
    except Exception:
        return False


def scrape_category(driver, paths: list[str]) -> list[dict]:
    all_products = []

    for path in paths:
        print(f"\n  Category: {BASE_URL}{path}")

        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}{path}?page={page}" if page > 1 else f"{BASE_URL}{path}"
            print(f"    Page {page}... ", end="", flush=True)

            driver.get(url)

            # Wait for product grid to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-layout"))
                )
            except Exception:
                print("timeout / no products")
                break

            time.sleep(DELAY)  # let JS finish rendering

            products = get_products_from_page(driver)

            if not products:
                print("no products")
                break

            all_products.extend(products)
            print(f"{len(products)} products")

            if not has_next_page(driver):
                break

    return all_products


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def extract_price(text: str) -> float:
    text = str(text).replace("₹", "").replace(",", "").strip()
    m = re.search(r"\d+\.?\d*", text)
    return float(m.group()) if m else 0.0


# ─────────────────────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────────────────────

def enrich_storage(df: pd.DataFrame) -> pd.DataFrame:
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
        return "AIO" if any(x in n for x in ["aio", "liquid", "240", "280", "360"]) else "Air"

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

def run(targets: list[str]):
    print("\nStarting browser...")
    driver = make_driver()

    # Visit homepage first to pick up cookies/session
    print("  Loading MDComputers homepage...")
    driver.get(BASE_URL)
    time.sleep(2)

    try:
        for target in targets:
            print(f"\n{'='*50}")
            print(f"  Scraping: {target.upper()}")
            print(f"{'='*50}")

            cfg      = CATEGORIES[target]
            products = scrape_category(driver, cfg["urls"])

            if not products:
                print(f"\n❌  No products found for {target}.")
                continue

            df  = pd.DataFrame(products).drop_duplicates(subset=["Name"]).reset_index(drop=True)
            df  = ENRICHERS[target](df)
            out = cfg["output"]
            df.to_csv(out, index=False)

            print(f"\n✔  {len(df)} products saved → {out}")
            print(df.head(3).to_string())

    finally:
        driver.quit()
        print("\n✅  Done! Move the CSVs into pc_builder_final/data_files/")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(CATEGORIES.keys())
    valid   = [t for t in targets if t in CATEGORIES]
    if not valid:
        print(f"Unknown target. Choose from: {list(CATEGORIES.keys())}")
        sys.exit(1)
    run(valid)


if __name__ == "__main__":
    main()
