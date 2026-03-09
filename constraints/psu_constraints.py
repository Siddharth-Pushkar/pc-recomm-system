"""
PSU & Full System Power Budget Constraints
==========================================
Covers:
  - GPU ↔ PSU wattage requirements
  - CPU ↔ PSU wattage requirements
  - Full system power budget (CPU + GPU + overhead)
  - PSU efficiency tier by budget
  - Combined CPU + GPU thresholds (450 W → 850 W, 550 W → 1000 W)
  - High-voltage / transient spike headroom
  - Content creator sustained-load rules

Doc ref: "PSU & POWER DELIVERY CONSTRAINTS"

PSU Formula (from team spec):
  Effective_CPU_Power = cpu_tdp × 1.25   (boost headroom)
  Mobo_Overhead       = ATX: 60W | mATX: 50W | ITX: 40W
  Total_System_Power  = Effective_CPU_Power + gpu_tdp + mobo_overhead
  Recommended_PSU     = Total_System_Power × 1.35  → round up to next tier
                        (35% headroom for GPU transient spikes)
"""
import re
from utils.helpers import get_watts, get_int, get_budget_tier
from config import PSU_SIZES


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_tdp(row, default: int) -> int:
    """Extract TDP watts from cpu or gpu row."""
    # Try common column names
    for col in ("TDP", "tdp"):
        if col in row.index:
            w = get_watts(row[col], 0)
            if w > 0:
                return w
    return default


def _get_mobo_overhead(mobo_row) -> int:
    """
    Estimate motherboard power overhead by form factor.
    ATX ≈ 60W | Micro ATX ≈ 50W | Mini ITX ≈ 40W
    [MOBO: Form Factor]
    """
    ff = str(mobo_row.get("Form Factor", mobo_row.get("form_factor", "ATX"))).upper()
    if "MINI" in ff or "ITX" in ff:
        return 40
    if "MICRO" in ff or "MATX" in ff or "M-ATX" in ff:
        return 50
    return 60  # ATX / EATX default


def _next_psu_tier(watts: int) -> int:
    """Round up to the next standard PSU wattage tier."""
    for tier in sorted(PSU_SIZES):
        if tier >= watts:
            return tier
    return PSU_SIZES[-1]  # return max if above all tiers


def _get_psu_wattage(psu_row) -> int:
    """Extract PSU wattage from psu['Wattage']"""
    # [PSU: Wattage]
    for col in ("Wattage", "wattage", "watts"):
        if col in psu_row.index:
            w = get_watts(psu_row[col], 0)
            if w > 0:
                return w
    # fallback: parse from Name
    name = str(psu_row.get("Name", psu_row.get("name", "")))
    m = re.search(r"(\d{3,4})\s*W", name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _get_psu_efficiency(psu_row) -> str:
    """Extract efficiency tier string from psu['Efficiency'] e.g. 'Gold'"""
    # [PSU: Efficiency]
    for col in ("Efficiency", "efficiency", "80+", "rating"):
        if col in psu_row.index:
            val = str(psu_row[col]).strip()
            if val:
                return val
    # fallback: parse from Name
    name = str(psu_row.get("Name", psu_row.get("name", ""))).upper()
    for tier in ("TITANIUM", "PLATINUM", "GOLD", "SILVER", "BRONZE"):
        if tier in name:
            return tier.capitalize()
    return "Bronze"


def _parse_gpu_connectors(ext_power_str: str):
    """
    Parse gpu['External Power'] to count 8-pin and 16-pin connectors.
    e.g. '2 x PCIe 8-pin' → (count_8pin=2, has_16pin=False)
         '1 x 16-pin 12VHPWR' → (count_8pin=0, has_16pin=True)
    Returns (num_8pin, has_16pin)
    """
    s = str(ext_power_str).lower()
    has_16 = "16-pin" in s or "12vhpwr" in s or "16pin" in s
    m = re.search(r"(\d+)\s*x\s*pcie\s*8", s)
    count_8 = int(m.group(1)) if m else (1 if "8-pin" in s and not has_16 else 0)
    return count_8, has_16


def _efficiency_rank(eff_str: str) -> int:
    """Higher = better efficiency tier."""
    mapping = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4, "titanium": 5}
    return mapping.get(eff_str.lower().strip(), 0)


# ── Required efficiency tier by budget ───────────────────────────────────────
# Content creator builds run sustained full load → efficiency is critical.
# [PSU: Efficiency]
_CC_MIN_EFFICIENCY = {
    "entry": "Bronze",
    "low":   "Gold",
    "mid":   "Gold",
    "high":  "Platinum",
    "ultra": "Platinum",
}

_GAMING_MIN_EFFICIENCY = {
    "entry": "Bronze",
    "low":   "Bronze",
    "mid":   "Gold",
    "high":  "Gold",
    "ultra": "Platinum",
}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONSTRAINT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def add_psu_constraints(model,
                        cpu_df, cpu_vars,
                        gpu_df, gpu_vars,
                        mobo_df, mobo_vars,
                        psu_df, psu_vars,
                        budget: int, use_case: str = "gaming"):
    """
    Apply GPU ↔ PSU, CPU ↔ PSU, and full system power budget constraints.

    Parameters
    ----------
    model      : CP-SAT CpModel
    cpu_df     : cleaned CPU dataframe
    cpu_vars   : BoolVar list
    gpu_df     : cleaned GPU dataframe
    gpu_vars   : BoolVar list
    mobo_df    : cleaned motherboard dataframe
    mobo_vars  : BoolVar list
    psu_df     : cleaned PSU dataframe
    psu_vars   : BoolVar list
    budget     : total build budget in INR
    use_case   : "gaming" | "productivity" | "content_creation"
    """

    tier  = get_budget_tier(budget)
    is_cc = (use_case == "content_creation")

    min_eff_map  = _CC_MIN_EFFICIENCY if is_cc else _GAMING_MIN_EFFICIENCY
    min_eff_str  = min_eff_map.get(tier, "Bronze")
    min_eff_rank = _efficiency_rank(min_eff_str)

    # ── STEP 1: Pre-filter PSU by efficiency tier ─────────────────────────────
    # Content creation sustained load makes efficiency directly measurable
    # in electricity cost and thermal stability.
    # [PSU: Efficiency]
    for p in range(len(psu_df)):
        psu_row = psu_df.loc[p]
        eff_str  = _get_psu_efficiency(psu_row)
        eff_rank = _efficiency_rank(eff_str)
        if eff_rank > 0 and eff_rank < min_eff_rank:
            model.Add(psu_vars[p] == 0)

    # ── STEP 2: Per CPU+GPU pair → required PSU wattage ──────────────────────
    # We iterate all CPU×GPU pairs, compute required wattage, then ensure
    # the selected PSU meets that requirement.
    #
    # Formula (team spec):
    #   Effective_CPU = cpu_tdp × 1.25
    #   Total         = Effective_CPU + gpu_tdp + mobo_overhead
    #   Required_PSU  = Total × 1.35 → round up to next tier
    #
    # We use a representative mobo overhead (ATX default = 60W) here since
    # we can't enumerate CPU×GPU×MOBO triples efficiently in CP-SAT.
    # The full triple check is done post-solve in the display/validation layer.
    # [CPU: TDP] [GPU: TDP] [PSU: Wattage]

    DEFAULT_MOBO_OVERHEAD = 60  # ATX default

    for c in range(len(cpu_df)):
        cpu_row = cpu_df.loc[c]
        cpu_tdp = _get_tdp(cpu_row, default=65)
        # Intel K/KS series can draw 125–140% of rated TDP under sustained boost
        # [CPU: TDP]
        cpu_name = str(cpu_row.get("Name", cpu_row.get("name", ""))).upper()
        if any(s in cpu_name for s in ["K ", "KF ", "KS "]):
            cpu_tdp = int(cpu_tdp * 1.25)  # effective sustained TDP
        effective_cpu = int(cpu_tdp * 1.25)

        for g in range(len(gpu_df)):
            gpu_row = gpu_df.loc[g]
            gpu_tdp = _get_tdp(gpu_row, default=150)
            gpu_name = str(gpu_row.get("Name", gpu_row.get("name", ""))).upper()

            total_draw   = effective_cpu + gpu_tdp + DEFAULT_MOBO_OVERHEAD
            required_raw = int(total_draw * 1.35)
            required_psu = _next_psu_tier(required_raw)

            # COMBINED THRESHOLD RULE (doc spec):
            # cpu_tdp + gpu_tdp ≥ 450W → PSU ≥ 850W
            # cpu_tdp + gpu_tdp ≥ 550W → PSU ≥ 1000W
            # [CPU: TDP] [GPU: TDP]
            combined = cpu_tdp + gpu_tdp
            if combined >= 550:
                required_psu = max(required_psu, 1000)
            elif combined >= 450:
                required_psu = max(required_psu, 850)

            # HIGH-POWER GPU RULES (doc spec):
            # GPU TDP ≥ 300W → PSU ≥ 850W  (transient spikes during rendering)
            # GPU TDP ≥ 400W → PSU ≥ 1000W (sustained workstation-class draw)
            # [GPU: TDP]
            if gpu_tdp >= 400:
                required_psu = max(required_psu, 1000)
            elif gpu_tdp >= 300:
                required_psu = max(required_psu, 850)

            # HIGH-TDP CPU RULE:
            # cpu_tdp ≥ 120W → PSU must be ≥ 750W for content creation
            # (simultaneous CPU + GPU rendering load)
            # [CPU: TDP]
            if is_cc and cpu_tdp >= 120:
                required_psu = max(required_psu, 750)

            # Now enforce: for this CPU+GPU pair, PSU wattage must ≥ required_psu
            for p in range(len(psu_df)):
                psu_row     = psu_df.loc[p]
                psu_wattage = _get_psu_wattage(psu_row)
                if psu_wattage > 0 and psu_wattage < required_psu:
                    # This PSU is too weak for this CPU+GPU pair
                    # If either this CPU or this GPU is selected, this PSU is blocked
                    model.Add(cpu_vars[c] + gpu_vars[g] + psu_vars[p] <= 2)

    # ── STEP 3: GPU power connector check ─────────────────────────────────────
    # GPU cannot operate if required PCIe connectors are unavailable.
    # A PSU lacking the correct connectors is a hard build failure.
    # [GPU: External Power]
    #
    # Strategy: flag extreme-connector GPUs (16-pin / 3×8-pin) and require
    # PSU wattage to be ≥ 850W as a proxy for having the right connectors.
    # (Full connector matching requires connector data in PSU CSV — proxy used here.)
    for g in range(len(gpu_df)):
        gpu_row   = gpu_df.loc[g]
        ext_power = str(gpu_row.get("External Power",
                                    gpu_row.get("external_power", "")))
        _, has_16pin = _parse_gpu_connectors(ext_power)

        if has_16pin:
            # 16-pin 12VHPWR connector GPUs (RTX 40/50 flagship series)
            # require PSU ≥ 850W and ideally a native 16-pin cable.
            # Block underpowered PSUs from pairing with these GPUs.
            for p in range(len(psu_df)):
                psu_wattage = _get_psu_wattage(psu_df.loc[p])
                if psu_wattage > 0 and psu_wattage < 850:
                    model.Add(gpu_vars[g] + psu_vars[p] <= 1)

    # ── STEP 4: Content creator absolute minimum PSU ──────────────────────────
    # Any content creator build using PSU < 650W is underpowered.
    # Sustained CPU + GPU rendering at full load will cause crashes.
    # [PSU: Wattage]
    if is_cc:
        for p in range(len(psu_df)):
            psu_wattage = _get_psu_wattage(psu_df.loc[p])
            if psu_wattage > 0 and psu_wattage < 650:
                model.Add(psu_vars[p] == 0)

    return model
