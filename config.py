"""
Configuration constants for PC Builder
"""

# ── Budget tiers (INR) ────────────────────────────────────────────────────
BUDGET_TIERS = {
    "entry": 100000,
    "low":   200000,
    "mid":   400000,
    "high":  700000,
    "ultra": float("inf"),
}

# ── Use-case performance weights (cpu_weight, gpu_weight) ─────────────────
USE_CASE_WEIGHTS = {
    "gaming":           (0.8,  2.6),
    "productivity":     (2.2,  0.8),
    "content_creation": (1.8,  1.4),
}

# ── PSU efficiency tiers by budget ────────────────────────────────────────
PSU_EFFICIENCY = [
    (130000,       "Bronze"),
    (250000,       "Gold"),
    (500000,       "Platinum"),
    (float("inf"), "Titanium"),
]

PSU_SIZES = [450, 550, 650, 750, 850, 1000, 1200, 1400, 1600]

# ── Circuit-based motherboard thresholds ──────────────────────────────────
VRM_TIERS = {
    "entry": 4,
    "low":   6,
    "mid":   8,
    "high":  10,
    "ultra": 12,
}

PCIE_MIN_VERSION = {
    "entry": 3,
    "low":   4,
    "mid":   4,
    "high":  5,
    "ultra": 5,
}

M2_MIN_SLOTS = {
    "entry": 1,
    "low":   2,
    "mid":   2,
    "high":  3,
    "ultra": 3,
}

USB_MIN_COUNT = {
    "entry": 4,
    "low":   6,
    "mid":   6,
    "high":  8,
    "ultra": 10,
}
