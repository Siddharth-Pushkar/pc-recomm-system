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

    # ══════════════════════════════════════════════════════════════
    # SECTION A — CIRCUIT-BASED CONSTRAINTS
    # ══════════════════════════════════════════════════════════════

    # A1. VRM Power Phases
    min_phases = VRM_TIERS.get(tier, 4)
    for m in range(len(mobo_df)):
        phases = get_vrm_phases(mobo_df.loc[m])
        if phases > 0 and phases < min_phases:
            model.Add(mobo_vars[m] == 0)

    # A2. PCIe Version
    min_pcie = PCIE_MIN_VERSION.get(tier, 4)
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
    min_m2 = M2_MIN_SLOTS.get(tier, 1)
    for m in range(len(mobo_df)):
        slots = get_m2_slots(mobo_df.loc[m])
        if slots > 0 and slots < min_m2:
            model.Add(mobo_vars[m] == 0)

    # A4. USB Count
    min_usb = USB_MIN_COUNT.get(tier, 4)
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
    for m in range(len(mobo_df)):
        mobo_name = str(mobo_df.loc[m, "Name"]).upper()

        # AMD
        if any(x in mobo_name for x in ["A620", "A520"]):
            if budget > 200000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B450", "B550", "B650"]):
            if budget > 450000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["X670", "X670E", "X870"]):
            if budget < 200000:
                model.Add(mobo_vars[m] == 0)

        # Intel
        elif any(x in mobo_name for x in ["H610", "H510", "H410"]):
            if budget > 200000:
                model.Add(mobo_vars[m] == 0)
        elif any(x in mobo_name for x in ["B660", "B760", "B560"]):
            if budget > 450000:
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
