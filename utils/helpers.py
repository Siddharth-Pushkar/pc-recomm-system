"""
Helper / utility functions
Merged from original helpers.py + data_cleaner.py + new circuit-based helpers
"""
import re
import math
import pandas as pd
from config import BUDGET_TIERS, PSU_SIZES, PSU_EFFICIENCY


# ═════════════════════════════════════════════════════════════════
# GENERIC EXTRACTORS  (from original helpers.py + data_cleaner.py)
# ═════════════════════════════════════════════════════════════════

def extract_number(value):
    """Extract first numeric value from any messy string."""
    if pd.isna(value):
        return 0
    value = str(value).replace("₹", "").replace("$", "").replace(",", "").strip()
    match = re.search(r"\d+\.?\d*", value)
    return float(match.group()) if match else 0


def get_watts(val, default=0) -> int:
    """Extract wattage integer from strings like '125W' or '125'."""
    try:
        return int(float(re.search(r"[\d.]+", str(val)).group()))
    except Exception:
        return default


def get_ghz(val, default=0.0) -> float:
    """Extract GHz float from strings like '4.7 GHz' or '4.7'."""
    try:
        return float(re.search(r"[\d.]+", str(val)).group())
    except Exception:
        return default


def get_int(val, default=0) -> int:
    return int(extract_number(val)) if extract_number(val) else default


def safe_column(df, col_name):
    """Return column if it exists, else a zero Series."""
    if col_name in df.columns:
        return df[col_name]
    print(f"  ⚠  Column '{col_name}' not found — filling with 0.")
    return pd.Series([0] * len(df))


# ═════════════════════════════════════════════════════════════════
# BUDGET HELPERS
# ═════════════════════════════════════════════════════════════════

def get_budget_tier(budget: int) -> str:
    if budget < BUDGET_TIERS["entry"]:
        return "entry"
    elif budget < BUDGET_TIERS["low"]:
        return "low"
    elif budget < BUDGET_TIERS["mid"]:
        return "mid"
    elif budget < BUDGET_TIERS["high"]:
        return "high"
    return "ultra"


def calculate_budget_range(budget: int):
    """
    Calculate (lower_limit, upper_limit) for the CP-SAT budget constraint.
    Matches original logic: core = 90% of budget, then a band around that.
    """
    core_budget = int(budget * 0.9)
    if budget <= 200000:
        lower = int(core_budget * 0.92)
        upper = int(core_budget * 1.02)
    else:
        lower = int(core_budget * 0.85)
        upper = int(core_budget * 1.10)
    return lower, upper


# ═════════════════════════════════════════════════════════════════
# CPU IDENTIFICATION  (from original helpers.py)
# ═════════════════════════════════════════════════════════════════

def intel_gen(name: str):
    """
    Returns (class, generation) for Intel CPUs.
    e.g. 'Core i5-13600K' → ('5', 13)
    """
    name = name.lower()
    m = re.search(r"i([3579])-(\d{2})", name)
    if m:
        return m.group(1), int(m.group(2))
    # Core Ultra
    m2 = re.search(r"ultra\s*([579])", name)
    if m2:
        return f"ultra{m2.group(1)}", 15  # treat Ultra as gen 15+
    return None, 0


def ryzen_gen(name: str):
    """
    Returns (class, generation) for AMD Ryzen CPUs.
    e.g. 'Ryzen 5 7600X' → ('5', 7)
    """
    name = name.lower()
    m = re.search(r"ryzen\s([3579])\s(\d)", name)
    return (m.group(1), int(m.group(2))) if m else (None, 0)


# ═════════════════════════════════════════════════════════════════
# GPU IDENTIFICATION  (from original helpers.py)
# ═════════════════════════════════════════════════════════════════

def extract_gpu_tier(name: str):
    """
    Returns (generation, tier) for NVIDIA/AMD GPUs.
    e.g. 'RTX 4070' → (40, 7),  'RX 7900 XTX' → (79, 0)
    Higher = better.
    """
    name = name.lower()
    match = re.search(r"(rtx|rx)\s*(\d{3,4})", name)
    if match:
        num = int(match.group(2))
        gen  = num // 10
        tier = num % 10
        return gen, tier
    return 0, 0


# ═════════════════════════════════════════════════════════════════
# MOTHERBOARD CIRCUIT HELPERS  (new)
# ═════════════════════════════════════════════════════════════════

def get_vrm_phases(mobo_row) -> int:
    """Extract VRM power phase count."""
    for col in ["VRM_Phases", "Power Phases", "VRM Phases"]:
        if col in mobo_row.index and mobo_row[col]:
            return get_int(mobo_row[col], 0)
    return 0


def get_pcie_version(mobo_row) -> int:
    """Extract primary PCIe slot version as integer."""
    for col in ["PCIe_Version", "PCIe Version", "PCI-E"]:
        if col in mobo_row.index and mobo_row[col]:
            m = re.search(r"(\d)", str(mobo_row[col]))
            return int(m.group()) if m else 0
    return 0


def get_m2_slots(mobo_row) -> int:
    """Extract number of M.2 slots."""
    for col in ["M2_Slots", "M.2 Slots", "M2 Slots"]:
        if col in mobo_row.index and mobo_row[col]:
            return get_int(mobo_row[col], 0)
    return 0


def get_usb_count(mobo_row) -> int:
    """Extract total USB port count."""
    for col in ["USB_Count", "USB Ports", "USB Count"]:
        if col in mobo_row.index and mobo_row[col]:
            return get_int(mobo_row[col], 0)
    return 0


def has_wifi(mobo_row) -> bool:
    """Check if motherboard has onboard WiFi."""
    for col in ["WiFi", "Wireless", "Wi-Fi"]:
        if col in mobo_row.index:
            val = str(mobo_row[col]).lower().strip()
            return val in ("yes", "true", "1", "wifi", "built-in", "integrated")
    return False


# ═════════════════════════════════════════════════════════════════
# PSU HELPERS
# ═════════════════════════════════════════════════════════════════

def calculate_psu(cpu_tdp: int, gpu_tdp: int, budget: int):
    """Return (wattage, efficiency_rating) for PSU recommendation."""
    total = cpu_tdp + gpu_tdp
    recommended = total * 2

    if budget <= 700000:
        recommended = min(recommended, 1200)
    else:
        recommended = max(recommended, 1400)

    psu_choice = min(PSU_SIZES, key=lambda x: abs(x - recommended))

    rating = "Bronze"
    for threshold, eff in PSU_EFFICIENCY:
        if budget <= threshold:
            rating = eff
            break

    return psu_choice, rating


# ═════════════════════════════════════════════════════════════════
# STORAGE HELPERS
# ═════════════════════════════════════════════════════════════════

def get_storage_capacity_gb(name: str) -> int:
    name = name.upper()
    m_tb = re.search(r"(\d+\.?\d*)\s*TB", name)
    m_gb = re.search(r"(\d+)\s*GB", name)
    if m_tb:
        return int(float(m_tb.group(1)) * 1024)
    elif m_gb:
        return int(m_gb.group(1))
    return 0


def is_nvme(name: str) -> bool:
    return any(x in name.upper() for x in ["NVME", "M.2", "PCIE"])
