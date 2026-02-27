"""
RAM-specific constraints (original logic preserved + capacity scaling)
"""

def add_ram_constraints(model, ram_df, ram_vars, cpu_vars, cpu_df, budget):

    # ── 1. Ban DDR3 for modern builds ─────────────────────────────────────
    if budget > 45000:
        for r in range(len(ram_df)):
            if "DDR3" in str(ram_df.loc[r, "Name"]):
                model.Add(ram_vars[r] == 0)

    # ── 2. Dual-channel only ───────────────────────────────────────────────
    for r in range(len(ram_df)):
        modules = str(ram_df.loc[r].get("Modules", ""))
        if "2 x" not in modules and "2x" not in modules.lower():
            model.Add(ram_vars[r] == 0)

    # ── 3. Platform DDR compatibility ─────────────────────────────────────
    for c in range(len(cpu_df)):
        cpu_socket = str(cpu_df.loc[c, "Socket"])
        for r in range(len(ram_df)):
            ram_name = str(ram_df.loc[r, "Name"])

            if "AM4" in cpu_socket and "DDR5" in ram_name:
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
            if "AM5" in cpu_socket and "DDR4" in ram_name:
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
            if "1200" in cpu_socket and "DDR5" in ram_name:
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)
            if "1851" in cpu_socket and "DDR4" in ram_name:
                model.Add(cpu_vars[c] + ram_vars[r] <= 1)

    # ── 4. Budget < 1.2L → DDR4 only ──────────────────────────────────────
    if budget < 120000:
        for r in range(len(ram_df)):
            if "DDR5" in str(ram_df.loc[r, "Name"]):
                model.Add(ram_vars[r] == 0)

    # ── 5. Budget > 1.2L → DDR5 preferred ────────────────────────────────
    if budget > 120000:
        for r in range(len(ram_df)):
            if "DDR4" in str(ram_df.loc[r, "Name"]):
                model.Add(ram_vars[r] == 0)

    # ── 6. Capacity scaling ────────────────────────────────────────────────
    for r in range(len(ram_df)):
        modules = str(ram_df.loc[r].get("Modules", ""))
        name    = str(ram_df.loc[r, "Name"])
        is_16gb = "2 x 8"  in modules or "2 x 8"  in name
        is_32gb = "2 x 16" in modules or "2 x 16" in name

        if budget > 200000 and is_16gb:
            model.Add(ram_vars[r] == 0)
        if budget > 700000 and is_32gb:
            model.Add(ram_vars[r] == 0)

    return model
