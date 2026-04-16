"""
Motherboard constraints

SECTION A — Circuit-Based (NEW)
  ✔ VRM power phases     — stable power delivery for the CPU tier
  ✔ PCIe version         — GPU bandwidth not bottlenecked
  ✔ M.2 slot count       — NVMe expandability
  ✔ USB port count       — connectivity
  ✔ WiFi                 — optional user requirement

SECTION B — Compatibility (from original mobo_constraints.py)
  ✔ CPU socket match
  ✔ Budget ↔ chipset tier
  ✔ High-end CPU/GPU must not use entry boards
"""
from utils.helpers import (
    get_budget_tier,
    get_vrm_phases, get_pcie_version, get_m2_slots, get_usb_count, has_wifi,
)
from config import VRM_TIERS, PCIE_MIN_VERSION, M2_MIN_SLOTS, USB_MIN_COUNT


def add_mobo_constraints(model, mobo_df, mobo_vars,
                         cpu_vars, cpu_df,
                         gpu_vars, gpu_df,
                         budget,
                         require_wifi=False):

    tier = get_budget_tier(budget)

    def _effective_min(min_by_tier, values):
        """
        Pick the strictest tier minimum that is still achievable
        with the current motherboard dataset. This avoids infeasible
        builds when the dataset lacks features like PCIe 5.0 or high
        USB counts at higher budgets.
        """
        order = ["entry", "low", "mid", "high", "ultra"]
        idx = order.index(tier)
        vals = [v for v in values if v > 0]
        if not vals:
            return min_by_tier[order[idx]]
        for j in range(idx, -1, -1):
            req = min_by_tier[order[j]]
            if any(v >= req for v in vals):
                return req
        return min_by_tier[order[0]]

    # ══════════════════════════════════════════════════════════════
    # SECTION A — CIRCUIT-BASED CONSTRAINTS
    # ══════════════════════════════════════════════════════════════

    # A1. VRM Power Phases
    min_phases = _effective_min(
        VRM_TIERS,
        [get_vrm_phases(mobo_df.loc[m]) for m in range(len(mobo_df))]
    )
    for m in range(len(mobo_df)):
        phases = get_vrm_phases(mobo_df.loc[m])
        if phases > 0 and phases < min_phases:
            model.Add(mobo_vars[m] == 0)

    # A2. PCIe Version
    min_pcie = _effective_min(
        PCIE_MIN_VERSION,
        [get_pcie_version(mobo_df.loc[m]) for m in range(len(mobo_df))]
    )
    for m in range(len(mobo_df)):
        pcie = get_pcie_version(mobo_df.loc[m])
        if pcie > 0 and pcie < min_pcie:
            model.Add(mobo_vars[m] == 0)

    # PCIe 5.0 required for flagship GPUs
    for g in range(len(gpu_df)):
        gpu_name = str(gpu_df.loc[g, "Name"]).lower()
        if any(x in gpu_name for x in ["5090", "5080", "5070", "7900 xtx"]):
            for m in range(len(mobo_df)):
                pcie = get_pcie_version(mobo_df.loc[m])
                if pcie > 0 and pcie < 5:
                    model.Add(gpu_vars[g] + mobo_vars[m] <= 1)

    # A3. M.2 Slots
    min_m2 = _effective_min(
        M2_MIN_SLOTS,
        [get_m2_slots(mobo_df.loc[m]) for m in range(len(mobo_df))]
    )
    for m in range(len(mobo_df)):
        slots = get_m2_slots(mobo_df.loc[m])
        if slots > 0 and slots < min_m2:
            model.Add(mobo_vars[m] == 0)

    # A4. USB Count
    min_usb = _effective_min(
        USB_MIN_COUNT,
        [get_usb_count(mobo_df.loc[m]) for m in range(len(mobo_df))]
    )
    for m in range(len(mobo_df)):
        usb = get_usb_count(mobo_df.loc[m])
        if usb > 0 and usb < min_usb:
            model.Add(mobo_vars[m] == 0)

    # A5. WiFi
    if require_wifi:
        for m in range(len(mobo_df)):
            if not has_wifi(mobo_df.loc[m]):
                model.Add(mobo_vars[m] == 0)

    # ══════════════════════════════════════════════════════════════
    # SECTION B — COMPATIBILITY CONSTRAINTS (original logic)
    # ══════════════════════════════════════════════════════════════

    # B1. CPU ↔ MOBO socket match
    for i in range(len(cpu_df)):
        cpu_socket = str(cpu_df.loc[i, "Socket"])
        for j in range(len(mobo_df)):
            mobo_socket = str(mobo_df.loc[j].get("Socket/CPU", mobo_df.loc[j].get("Socket", "")))
            if cpu_socket not in mobo_socket:
                model.Add(cpu_vars[i] + mobo_vars[j] <= 1)

    # B2. Budget tier ↔ chipset tier
    #
    # Rule: don't over-restrict. The goal is to prevent mismatches
    # (e.g. entry board at ultra budget), not to force the most
    # expensive board at every tier.
    #
    # AMD tier thresholds:
    #   A320/A520/A620   — block above ₹2L (entry chipsets only)
    #   B450/B550        — block above ₹5L (AM4 boards, getting old)
    #   B650/B840/B850   — block above ₹7L (mid AM5, fine up to ultra)
    #   X670/X870 series — block below ₹2L (too expensive for entry)
    #
    # Intel tier thresholds:
    #   H610/H510/H410   — block above ₹2L (entry only)
    #   B560/B660        — block above ₹5L (older B-series)
    #   B760/B860        — block above ₹7L (current B-series, fine at high)
    #   Z690/Z790/Z890   — block below ₹2L (too expensive for entry)

    for m in range(len(mobo_df)):
        mobo_name = str(mobo_df.loc[m, "Name"]).upper()

        # AMD
        if any(x in mobo_name for x in ["A320", "A520", "A620"]):
            if budget > 200000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B450", "B550"]):
            if budget > 500000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B650", "B840", "B850"]):
            if budget > 700000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["X670", "X670E", "X870", "X870E"]):
            if budget < 200000:
                model.Add(mobo_vars[m] == 0)

        # Intel
        elif any(x in mobo_name for x in ["H610", "H510", "H410", "H810"]):
            if budget > 200000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B560", "B660"]):
            if budget > 500000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B760", "B860"]):
            if budget > 700000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["Z690", "Z790", "Z890"]):
            if budget < 200000:
                model.Add(mobo_vars[m] == 0)

    # B3. High-end CPU must not use entry-level board
    for c in range(len(cpu_df)):
        cpu_price = cpu_df.loc[c, "price"]
        for m in range(len(mobo_df)):
            mobo_name = str(mobo_df.loc[m, "Name"])
            if cpu_price > 35000:
                if any(x in mobo_name for x in ["H610", "H510", "A520", "B450"]):
                    model.Add(cpu_vars[c] + mobo_vars[m] <= 1)

    # B4. High-tier GPU must not use entry-level board
    for g in range(len(gpu_df)):
        gpu_name = str(gpu_df.loc[g, "Name"])
        for m in range(len(mobo_df)):
            mobo_name = str(mobo_df.loc[m, "Name"])
            if any(x in gpu_name for x in ["7900", "5080", "5090", "4090"]):
                if any(x in mobo_name for x in ["A620", "H610", "H510"]):
                    model.Add(gpu_vars[g] + mobo_vars[m] <= 1)

    return model
