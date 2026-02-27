"""
GPU-specific constraints
"""
from utils.helpers import extract_gpu_tier, extract_number, get_budget_tier


def add_gpu_constraints(model, gpu_df, gpu_vars, budget,
                        cpu_vars, cpu_df,
                        use_case="gaming"):

    tier = get_budget_tier(budget)

    # ── 1. High-budget NVIDIA preference (original rule) ──────────────────
    if budget > 200000:
        for g in range(len(gpu_df)):
            name = str(gpu_df.loc[g, "Name"]).lower()
            if not any(x in name for x in ["rtx", "rx ", "radeon", "geforce", "arc"]):
                model.Add(gpu_vars[g] == 0)

    # ── 2. Minimum VRAM floor ──────────────────────────────────────────────
    for g in range(len(gpu_df)):
        vram = int(extract_number(gpu_df.loc[g].get("vram", gpu_df.loc[g].get("Memory", 4))) or 4)
        if use_case == "content_creation" and vram < 8:
            model.Add(gpu_vars[g] == 0)
        elif tier in ("mid", "high", "ultra") and vram < 8:
            model.Add(gpu_vars[g] == 0)
        elif vram < 4:
            model.Add(gpu_vars[g] == 0)

    # ── 3. CPU ↔ GPU tier pairing (original gpu_constraints.py) ──────────
    for c in range(len(cpu_df)):
        cpu_name = str(cpu_df.loc[c, "Name"])
        for g in range(len(gpu_df)):
            gpu_name = str(gpu_df.loc[g, "Name"])

            if any(x in gpu_name for x in ["5060", "3050", "3060", "7600", "6600"]):
                if not any(x in cpu_name for x in ["i5", "Ryzen 5"]):
                    model.Add(cpu_vars[c] + gpu_vars[g] <= 1)
            elif any(x in gpu_name for x in ["5070", "4070", "7800", "7700"]):
                if not any(x in cpu_name for x in ["i5", "i7", "Ryzen 5", "Ryzen 7"]):
                    model.Add(cpu_vars[c] + gpu_vars[g] <= 1)
            elif any(x in gpu_name for x in ["5080", "5090", "4090", "7900"]):
                if not any(x in cpu_name for x in ["i7", "i9", "Ultra 7", "Ultra 9", "Ryzen 7", "Ryzen 9"]):
                    model.Add(cpu_vars[c] + gpu_vars[g] <= 1)

    # ── 4. GPU generation dominance (original gpu_constraints.py) ─────────
    for g1 in range(len(gpu_df)):
        name1  = str(gpu_df.loc[g1, "Name"])
        price1 = gpu_df.loc[g1, "price"]
        gen1, tier1 = extract_gpu_tier(name1)

        for g2 in range(len(gpu_df)):
            if g1 == g2:
                continue
            name2  = str(gpu_df.loc[g2, "Name"])
            price2 = gpu_df.loc[g2, "price"]
            gen2, tier2 = extract_gpu_tier(name2)

            if abs(price1 - price2) <= 3000:
                if gen2 > gen1 or (gen2 == gen1 and tier2 > tier1):
                    model.Add(gpu_vars[g1] <= gpu_vars[g2])

    return model
