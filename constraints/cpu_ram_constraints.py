"""
CPU ↔ RAM Constraints  (Generation, Speed Limits, Channels)
=============================================================
Covers:
  - AM4 → DDR4 only, AM5 → DDR5 only
  - LGA1700 deferred to mobo Memory Type check
  - Maximum supported memory
  - High-voltage kit → high-end chipset only
  - 64 GB config: prefer 2×32 over 4×16
  - 4-DIMM AM5 speed penalty awareness

Doc ref: "CPU ↔ RAM CONSTRAINTS (Generation, Speed Limits, Channels)"
"""
import re
from utils.helpers import get_int, get_budget_tier


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_ddr_type(speed_str: str) -> str:
    m = re.match(r"(DDR\d+)", str(speed_str).strip().upper())
    return m.group(1) if m else ""


def _parse_modules(modules_str: str):
    """Returns (sticks, per_stick_gb, total_gb)"""
    s = str(modules_str).replace(" ", "").upper()
    m = re.match(r"(\d+)X(\d+)GB", s)
    if m:
        sticks    = int(m.group(1))
        per_stick = int(m.group(2))
        return sticks, per_stick, sticks * per_stick
    m2 = re.search(r"(\d+)GB", s)
    if m2:
        total = int(m2.group(1))
        return 1, total, total
    return 0, 0, 0


def _parse_max_memory_gb(val) -> int:
    """cpu['Maximum Supported Memory'] e.g. '128 GB' → 128"""
    m = re.search(r"(\d+)", str(val))
    return int(m.group(1)) if m else 0


def _get_cpu_socket(cpu_row) -> str:
    # [CPU: Socket]
    return str(cpu_row.get("Socket", cpu_row.get("socket", ""))).strip().upper()


def _get_voltage(ram_row) -> float:
    # [RAM: Voltage]
    val = str(ram_row.get("Voltage", ram_row.get("voltage", "1.35")))
    m = re.search(r"[\d.]+", val)
    return float(m.group()) if m else 1.35


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONSTRAINT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def add_cpu_ram_constraints(model, cpu_df, cpu_vars,
                            ram_df, ram_vars,
                            mobo_df, mobo_vars,
                            budget: int, use_case: str = "gaming"):
    """
    Apply CPU ↔ RAM generation, speed-limit, and channel constraints.

    Parameters
    ----------
    model      : CP-SAT CpModel
    cpu_df     : cleaned CPU dataframe
    cpu_vars   : list of BoolVar, one per CPU row
    ram_df     : cleaned RAM dataframe
    ram_vars   : list of BoolVar, one per RAM row
    mobo_df    : cleaned motherboard dataframe (needed for LGA1700 DDR check)
    mobo_vars  : list of BoolVar, one per MOBO row
    budget     : total build budget in INR
    use_case   : "gaming" | "productivity" | "content_creation"
    """

    tier = get_budget_tier(budget)
    is_cc = (use_case == "content_creation")

    for c in range(len(cpu_df)):
        cpu_row  = cpu_df.loc[c]
        socket   = _get_cpu_socket(cpu_row)
        # [CPU: Maximum Supported Memory]
        max_mem  = _parse_max_memory_gb(
            cpu_row.get("Maximum Supported Memory",
                        cpu_row.get("maximum_supported_memory", "128 GB"))
        )

        for r in range(len(ram_df)):
            ram_row   = ram_df.loc[r]
            speed_str = ram_row.get("Speed", ram_row.get("speed", ""))
            ddr_type  = _get_ddr_type(speed_str)
            sticks, per_stick, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            voltage = _get_voltage(ram_row)

            # HARD RULE 1 — AM4 → DDR4 only
            # AM4 CPUs have no DDR5 support; the socket physically does not
            # expose DDR5 signals. Any DDR5 kit is incompatible.
            # [CPU: Socket] [RAM: Speed]
            if socket == "AM4" and ddr_type == "DDR5":
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
                continue

            # HARD RULE 2 — AM5 → DDR5 only
            # AM5 dropped DDR4 support entirely. DDR4 kits cannot be used.
            # [CPU: Socket] [RAM: Speed]
            if socket == "AM5" and ddr_type == "DDR4":
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
                continue

            # HARD RULE 3 — LGA1200 → DDR4 only
            # Intel 10th/11th gen (Comet Lake, Rocket Lake) are DDR4-only.
            # [CPU: Socket] [RAM: Speed]
            if socket == "LGA1200" and ddr_type == "DDR5":
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
                continue

            # NOTE — LGA1700 can be DDR4 or DDR5 depending on the motherboard.
            # This cannot be resolved at the CPU ↔ RAM level alone.
            # The check mobo['Memory Type'] == ram DDR type is enforced in
            # mobo_ram_constraints.py (HARD RULE 1 there).
            # [CPU: Socket] [MOBO: Memory Type]

            # HARD RULE 4 — Total RAM must not exceed cpu['Maximum Supported Memory']
            # [CPU: Maximum Supported Memory]
            if max_mem > 0 and total_gb > max_mem:
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
                continue

            # HARD RULE 5 — High-voltage RAM (≥ 1.45 V) → high-end chipset only
            # Budget VRMs feeding RAM voltage rails can be unstable at 1.45V+.
            # We enforce this CPU-side by only allowing high-voltage kits with
            # CPUs that pair with high-end chipsets (X570/X670/Z790/Z890).
            # Detection: use socket as proxy (AM5 high-end, LGA1700 high-end).
            # Full chipset check is in mobo_ram_constraints.py.
            # [RAM: Voltage] [CPU: Socket]
            if voltage >= 1.45:
                # Only allow on AM5 or LGA1700/LGA1851 (modern platforms
                # that have the VRM quality to handle extreme voltages)
                if socket not in ("AM5", "LGA1700", "LGA1851"):
                    model.Add(cpu_vars[c] + ram_vars[r] <= 1)

            # ── CONTENT CREATOR RULES ─────────────────────────────────────

            if is_cc:
                # CC RULE 1 — 4-DIMM config on AM5: flag speed drop
                # AM5 memory controller with 4 DIMMs loses stable speed headroom.
                # Avoid recommending 4-stick kits on AM5 above DDR5-6000.
                # [RAM: Modules] [CPU: Socket]
                if socket == "AM5" and sticks == 4:
                    import re as _re
                    mt = int(_re.search(r"DDR\d+-(\d+)", speed_str.upper()).group(1)) \
                         if _re.search(r"DDR\d+-(\d+)", speed_str.upper()) else 0
                    if mt > 6000:
                        # Soft-block: don't hard eliminate but disfavour
                        # by adding as a conditional: flag for solver to skip
                        # unless no better option exists.
                        # Implementation: treat as hard block at high/ultra
                        # where 2×32 GB is affordable.
                        if tier in ("high", "ultra"):
                            model.Add(cpu_vars[c] + ram_vars[r] <= 1)

                # CC RULE 2 — prefer 2×32 over 4×16 for 64 GB builds
                # 4-stick config fills all slots (no upgrade path) and
                # increases memory controller load.
                # Hard-block 4×16 at high/ultra tier where 2×32 is reachable.
                # [RAM: Modules] [MOBO: Memory Slots]
                if sticks == 4 and per_stick == 16 and tier in ("high", "ultra"):
                    model.Add(cpu_vars[c] + ram_vars[r] <= 1)

    return model
