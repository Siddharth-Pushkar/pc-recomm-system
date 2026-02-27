"""
Data cleaning for all component CSVs.
Extends the original data_cleaner.py to cover Storage, PSU, and Cooler.
"""
import pandas as pd
from utils.helpers import extract_number, safe_column


# ═══════════════════════════════════════════════
# CPU  (original logic preserved)
# ═══════════════════════════════════════════════

def clean_cpu_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price"]       = safe_column(df, "Price (INR Formatted)").apply(extract_number)
    df["cores"]       = safe_column(df, "Core Count").apply(extract_number)
    df["tdp"]         = safe_column(df, "TDP").apply(extract_number)
    df["base_clock"]  = safe_column(df, "Performance Core Clock").apply(extract_number)
    df["boost_clock"] = safe_column(df, "Performance Core Boost Clock").apply(extract_number)
    # Keep original columns too (constraints read them by original name)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# GPU  (original logic preserved)
# ═══════════════════════════════════════════════

def clean_gpu_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price"]       = safe_column(df, "Price").apply(extract_number)
    df["vram"]        = safe_column(df, "Memory").apply(extract_number)
    df["tdp"]         = safe_column(df, "TDP").apply(extract_number)
    df["boost_clock"] = safe_column(df, "Boost Clock").apply(extract_number)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# MOTHERBOARD  (original + new circuit columns)
# ═══════════════════════════════════════════════

def clean_mobo_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price"]    = safe_column(df, "Price").apply(extract_number)
    df["ram_slots"] = safe_column(df, "Memory Slots").apply(extract_number)
    df["ram_max"]   = safe_column(df, "Memory Max").apply(extract_number)

    # Circuit columns — read as-is (constraints handle missing gracefully)
    # Expected CSV columns: VRM_Phases, PCIe_Version, M2_Slots, USB_Count, WiFi
    for col in ["VRM_Phases", "PCIe_Version", "M2_Slots", "USB_Count", "WiFi"]:
        if col not in df.columns:
            print(f"  ⚠  Motherboard CSV missing '{col}' column — circuit filter for this metric disabled.")

    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# RAM  (original logic preserved)
# ═══════════════════════════════════════════════

def clean_ram_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price"]     = safe_column(df, "Price").apply(extract_number)
    df["speed_mhz"] = safe_column(df, "Speed").apply(extract_number)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# STORAGE  (new)
# ═══════════════════════════════════════════════

def clean_storage_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Try common price column names
    for col in ["Price (INR Formatted)", "Price", "price", "MRP"]:
        if col in df.columns:
            df["price"] = df[col].apply(extract_number)
            break
    if "price" not in df.columns:
        df["price"] = 0

    # Standardise Name column
    for col in ["Name", "Product", "Model"]:
        if col in df.columns:
            df["Name"] = df[col].astype(str).str.strip()
            break

    df["capacity_gb"] = safe_column(df, "Capacity").apply(extract_number)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# PSU  (new)
# ═══════════════════════════════════════════════

def clean_psu_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["Price (INR Formatted)", "Price", "price"]:
        if col in df.columns:
            df["price"] = df[col].apply(extract_number)
            break
    if "price" not in df.columns:
        df["price"] = 0

    for col in ["Name", "Product", "Model"]:
        if col in df.columns:
            df["Name"] = df[col].astype(str).str.strip()
            break

    df["wattage"] = safe_column(df, "Wattage").apply(extract_number)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
# COOLER  (new)
# ═══════════════════════════════════════════════

def clean_cooler_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["Price (INR Formatted)", "Price", "price"]:
        if col in df.columns:
            df["price"] = df[col].apply(extract_number)
            break
    if "price" not in df.columns:
        df["price"] = 0

    for col in ["Name", "Product", "Model"]:
        if col in df.columns:
            df["Name"] = df[col].astype(str).str.strip()
            break

    df["tdp_rating"] = safe_column(df, "TDP_Rating").apply(extract_number)
    df = df[df["price"] > 0].reset_index(drop=True)
    return df
