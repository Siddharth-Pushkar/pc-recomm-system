"""
CPU-specific constraints
"""
from utils.helpers import get_int, get_ghz, intel_gen, ryzen_gen, get_budget_tier, extract_number


def add_cpu_constraints(model, cpu_df, cpu_vars, budget,
                        gpu_vars, gpu_df,
                        mobo_vars, mobo_df,
                        ram_vars, ram_df,
                        use_case="gaming"):

    tier = get_budget_tier(budget)

    # ── 1. Minimum CPU floor ───────────────────────────────────────────────
    for i in range(len(cpu_df)):
        name  = str(cpu_df.loc[i, "Name"]).lower()
        cores = extract_number(cpu_df.loc[i].get("Core Count", 4))
        boost = extract_number(cpu_df.loc[i].get("Performance Core Boost Clock", 0))
        tdp   = extract_number(cpu_df.loc[i].get("TDP", 65))

        # Ban office/embedded chips
        if any(x in name for x in ["celeron", "pentium", "athlon", "silver", "n100", "n200"]):
            model.Add(cpu_vars[i] == 0)
            continue

        if cores < 4:
            model.Add(cpu_vars[i] == 0)
            continue

        if use_case in ("gaming", "content_creation") and boost < 3.5:
            model.Add(cpu_vars[i] == 0)
            continue

        if tdp < 35:
            model.Add(cpu_vars[i] == 0)
            continue

    # ── 2. Use-case core count minimums ───────────────────────────────────
    if use_case == "productivity":
        for i in range(len(cpu_df)):
            if extract_number(cpu_df.loc[i].get("Core Count", 4)) < 8:
                model.Add(cpu_vars[i] == 0)
    elif use_case == "content_creation":
        for i in range(len(cpu_df)):
            if extract_number(cpu_df.loc[i].get("Core Count", 4)) < 6:
                model.Add(cpu_vars[i] == 0)

    # ── 3. Flagship CPU for high/ultra budgets ────────────────────────────
    if tier in ("high", "ultra"):
        for i in range(len(cpu_df)):
            name = str(cpu_df.loc[i, "Name"]).lower()
            if not any(x in name for x in ["ryzen 9", "i9", "ultra 9", "9950", "9900"]):
                model.Add(cpu_vars[i] == 0)

    # ── 4. CPU generation upgrade rule (same as original solver.py) ───────
    for i in range(len(cpu_df)):
        name_i  = str(cpu_df.loc[i, "Name"])
        price_i = cpu_df.loc[i, "price"]
        ci, gi  = intel_gen(name_i)
        ca, ga  = ryzen_gen(name_i)

        for j in range(len(cpu_df)):
            if i == j:
                continue
            name_j  = str(cpu_df.loc[j, "Name"])
            price_j = cpu_df.loc[j, "price"]
            cj, gj  = intel_gen(name_j)
            caj, gaj = ryzen_gen(name_j)

            if abs(price_i - price_j) <= 3000:
                if ci and ci == cj and gi < gj:
                    model.Add(cpu_vars[i] == 0)
                if ca and ca == caj and ga < gaj:
                    model.Add(cpu_vars[i] == 0)

    # ── 5. CPU ↔ GPU bottleneck prevention ────────────────────────────────
    for c in range(len(cpu_df)):
        cpu_name = str(cpu_df.loc[c, "Name"]).lower()
        for g in range(len(gpu_df)):
            gpu_name = str(gpu_df.loc[g, "Name"]).lower()
            if any(x in gpu_name for x in ["5090", "5080", "4090", "7900 xtx"]):
                if any(x in cpu_name for x in ["ryzen 2", "8700", "9700", "6700", "ryzen 3000"]):
                    model.Add(cpu_vars[c] + gpu_vars[g] <= 1)

    # ── 6. Platform era consistency (from original cpu_constraints.py) ────
    for c in range(len(cpu_df)):
        cpu_name = str(cpu_df.loc[c, "Name"]).lower()
        for m in range(len(mobo_df)):
            mobo_name = str(mobo_df.loc[m, "Name"]).lower()
            if any(x in cpu_name for x in ["9700", "8700", "7700", "6700"]):
                if not any(x in mobo_name for x in ["z390", "b360", "z370", "h370"]):
                    model.Add(cpu_vars[c] + mobo_vars[m] <= 1)
            if any(x in cpu_name for x in ["5600", "5700", "5800", "5900", "10400", "10700", "11700"]):
                if any(x in mobo_name for x in ["h110", "b150", "b250", "h170"]):
                    model.Add(cpu_vars[c] + mobo_vars[m] <= 1)

    return model
