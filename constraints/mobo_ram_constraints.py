"""
Motherboard ↔ RAM Compatibility Constraints
=============================================
Covers:
  - DDR type match (hard incompatibility)
  - Capacity limits
  - Slot count limits
  - Dual-channel enforcement
  - ECC/Registered filter
  - Speed sweet-spot preferences
  - Content creator capacity floors (32 GB / 64 GB)

Doc ref: "MOTHERBOARD ↔ RAM COMPATIBILITY"
"""
import re
from utils.helpers import get_int, get_budget_tier


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_ddr_type(speed_str: str) -> str:
    """
    Extract DDR generation string from ram['Speed'].
    'DDR5-6000' → 'DDR5',  'DDR4-3600' → 'DDR4'
    """
    m = re.match(r"(DDR\d+)", str(speed_str).strip().upper())
    return m.group(1) if m else ""


def _get_ram_speed_mt(speed_str: str) -> int:
    """
    Extract MT/s integer from ram['Speed'].
    'DDR5-6000' → 6000
    """
    m = re.search(r"DDR\d+-(\d+)", str(speed_str).upper())
    return int(m.group(1)) if m else 0


def _parse_modules(modules_str: str):
    """
    Parse ram['Modules'] e.g. '2 x 16GB' → (sticks=2, per_stick_gb=16, total_gb=32)
    Returns (sticks, per_stick_gb, total_gb)
    """
    s = str(modules_str).replace(" ", "").upper()
    m = re.match(r"(\d+)X(\d+)GB", s)
    if m:
        sticks     = int(m.group(1))
        per_stick  = int(m.group(2))
        return sticks, per_stick, sticks * per_stick
    # fallback: single number like '32GB'
    m2 = re.search(r"(\d+)GB", s)
    if m2:
        total = int(m2.group(1))
        return 1, total, total
    return 0, 0, 0


def _parse_memory_max_gb(mem_max_str: str) -> int:
    """Parse mobo['Memory Max'] e.g. '128 GB' → 128"""
    m = re.search(r"(\d+)", str(mem_max_str))
    return int(m.group(1)) if m else 0


def _mobo_supported_speeds(speed_list_str: str):
    """
    Parse mobo['Memory Speed'] comma-separated list into a set of MT/s ints.
    'DDR5-4800, DDR5-6000' → {4800, 6000}
    Returns empty set if unparseable (means no restriction enforced).
    """
    speeds = set()
    for token in str(speed_list_str).split(","):
        m = re.search(r"DDR\d+-(\d+)", token.strip().upper())
        if m:
            speeds.add(int(m.group(1)))
    return speeds


def _is_ecc_registered(ram_row) -> bool:
    # [RAM: ECC / Registered]
    val = str(ram_row.get("ECC / Registered", "")).lower()
    return "ecc" in val or "registered" in val


def _get_mobo_memory_type(mobo_row) -> str:
    # [MOBO: Memory Type]
    return str(mobo_row.get("Memory Type", "")).strip().upper()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONSTRAINT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def add_mobo_ram_constraints(model, mobo_df, mobo_vars,
                             ram_df, ram_vars,
                             budget: int, use_case: str = "gaming"):
    """
    Apply Motherboard ↔ RAM compatibility and use-case constraints.

    Parameters
    ----------
    model      : CP-SAT CpModel
    mobo_df    : cleaned motherboard dataframe
    mobo_vars  : list of BoolVar, one per MOBO row
    ram_df     : cleaned RAM dataframe
    ram_vars   : list of BoolVar, one per RAM row
    budget     : total build budget in INR
    use_case   : "gaming" | "productivity" | "content_creation"
    """

    tier = get_budget_tier(budget)
    is_cc = (use_case == "content_creation")

    # ── PRE-FILTER: eliminate ECC / Registered RAM globally ──────────────────
    # Consumer motherboards do not support ECC Registered DIMMs.
    # These are server/workstation parts and must never appear in consumer builds.
    # [RAM: ECC / Registered]
    for r in range(len(ram_df)):
        if _is_ecc_registered(ram_df.loc[r]):
            model.Add(ram_vars[r] == 0)

    # ── PRE-FILTER: content creator RAM capacity floors ───────────────────────
    # Video timelines, 3D scenes, and compositor buffers all live in RAM.
    # 16 GB is insufficient for any sustained content creation workload.
    # [RAM: Modules]
    if is_cc:
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            sticks, per_stick, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0:
                # Hard floor: 32 GB minimum for all content creator builds
                if total_gb < 32:
                    model.Add(ram_vars[r] == 0)
                # Preferred floor for mid+ tier: 64 GB
                # Enforced as hard constraint at high/ultra where budget allows
                if tier in ("high", "ultra") and total_gb < 64:
                    model.Add(ram_vars[r] == 0)

    # ── PRE-FILTER: enforce dual-channel (2-stick minimum) ───────────────────
    # Single-channel RAM halves memory bandwidth.
    # For content creation this is measurable in render and export times.
    # For all use cases, single-stick is always suboptimal — block it.
    # [RAM: Modules]
    for r in range(len(ram_df)):
        ram_row = ram_df.loc[r]
        sticks, _, _ = _parse_modules(
            ram_row.get("Modules", ram_row.get("modules", ""))
        )
        if sticks == 1:
            model.Add(ram_vars[r] == 0)

    # ── PRE-FILTER: block extreme-speed RAM for content creator ───────────────
    # DDR5-7200+ gives marginal bandwidth gains but introduces XMP instability
    # during long sustained renders. Not worth the risk.
    # [RAM: Speed]
    if is_cc:
        for r in range(len(ram_df)):
            ram_row  = ram_df.loc[r]
            speed_mt = _get_ram_speed_mt(
                ram_row.get("Speed", ram_row.get("speed", ""))
            )
            ddr_type = _get_ddr_type(
                ram_row.get("Speed", ram_row.get("speed", ""))
            )
            if ddr_type == "DDR5" and speed_mt > 7200:
                model.Add(ram_vars[r] == 0)

    # ── PAIRWISE: MOBO ↔ RAM ─────────────────────────────────────────────────
    for m in range(len(mobo_df)):
        mobo_row      = mobo_df.loc[m]
        mobo_mem_type = _get_mobo_memory_type(mobo_row)
        # [MOBO: Memory Max]
        mobo_max_gb   = _parse_memory_max_gb(
            mobo_row.get("Memory Max", mobo_row.get("memory_max", "0"))
        )
        # [MOBO: Memory Slots]
        mobo_slots    = get_int(
            mobo_row.get("Memory Slots", mobo_row.get("memory_slots", 0)), 0
        )
        # [MOBO: Memory Speed] — set of supported MT/s values
        mobo_speeds   = _mobo_supported_speeds(
            mobo_row.get("Memory Speed", mobo_row.get("memory_speed", ""))
        )

        for r in range(len(ram_df)):
            ram_row  = ram_df.loc[r]
            ram_speed_str = ram_row.get("Speed", ram_row.get("speed", ""))
            ddr_type      = _get_ddr_type(ram_speed_str)
            speed_mt      = _get_ram_speed_mt(ram_speed_str)
            sticks, per_stick, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )

            # HARD RULE 1 — DDR type must match mobo['Memory Type']
            # DDR4 and DDR5 are physically incompatible (different notch, pin count).
            # [RAM: Speed] [MOBO: Memory Type]
            if ddr_type and mobo_mem_type and ddr_type not in mobo_mem_type:
                model.Add(mobo_vars[m] + ram_vars[r] <= 1)
                continue  # no point checking further rules for this pair

            # HARD RULE 2 — Total RAM capacity must not exceed mobo['Memory Max']
            # [MOBO: Memory Max] [RAM: Modules]
            if mobo_max_gb > 0 and total_gb > mobo_max_gb:
                model.Add(mobo_vars[m] + ram_vars[r] <= 1)
                continue

            # HARD RULE 3 — Stick count must not exceed mobo['Memory Slots']
            # [MOBO: Memory Slots] [RAM: Modules]
            if mobo_slots > 0 and sticks > mobo_slots:
                model.Add(mobo_vars[m] + ram_vars[r] <= 1)
                continue

            # SOFT RULE 4 — RAM speed must be in mobo's validated speed list
            # XMP profiles beyond validated speeds cause POST failures.
            # Only enforce when the mobo has a non-empty speed list.
            # [MOBO: Memory Speed] [RAM: Speed]
            if mobo_speeds and speed_mt > 0 and speed_mt not in mobo_speeds:
                # Use soft block: prefer not to pair but don't hard-fail
                # (some boards support unlisted speeds via JEDEC fallback)
                # For high-voltage extreme-speed kits, make it hard
                ram_voltage = float(
                    str(ram_row.get("Voltage", ram_row.get("voltage", "1.35")))
                    .replace("V", "").strip() or 1.35
                )
                if ram_voltage >= 1.45:
                    model.Add(mobo_vars[m] + ram_vars[r] <= 1)

    # ── CONTENT CREATOR: 4-slot mobo preferred ───────────────────────────────
    # 4-slot configs allow 64 GB with 2×32 GB kits (cheaper, leaves upgrade room).
    # At high/ultra budget: hard-require 4 slots.
    # [MOBO: Memory Slots]
    if is_cc and tier in ("high", "ultra"):
        for m in range(len(mobo_df)):
            mobo_row = mobo_df.loc[m]
            slots = get_int(
                mobo_row.get("Memory Slots", mobo_row.get("memory_slots", 0)), 0
            )
            if slots > 0 and slots < 4:
                model.Add(mobo_vars[m] == 0)

    return model
