"""
Cooler constraints — TDP coverage, AIO vs air, room conditions, budget tier
"""
from utils.helpers import get_watts, get_budget_tier


def add_cooler_constraints(model, cooler_df, cooler_vars,
                           cpu_df, cpu_vars, budget,
                           room_condition="no"):

    tier       = get_budget_tier(budget)
    dusty_warm = room_condition.strip().lower() in ("yes", "y")

    for k in range(len(cooler_df)):
        name       = str(cooler_df.loc[k, "Name"]).lower()
        tdp_rating = get_watts(cooler_df.loc[k].get("TDP_Rating", cooler_df.loc[k].get("Max TDP", 0)), 0)
        is_aio     = "aio" in name or "liquid" in name or "360" in name or "240" in name

        # Mid+ builds need at least 240mm AIO or high-end air
        if tier in ("mid", "high", "ultra"):
            has_240    = "240" in name
            has_360    = "360" in name
            high_air   = any(x in name for x in ["noctua", "be quiet", "ak620", "nh-d15", "peerless"])
            if not (has_240 or has_360 or high_air):
                model.Add(cooler_vars[k] == 0)

        # Ultra builds need 360mm AIO
        if tier == "ultra" and "360" not in name:
            model.Add(cooler_vars[k] == 0)

        # Dusty/warm room → AIO only for mid+
        if dusty_warm and tier in ("mid", "high", "ultra") and not is_aio:
            model.Add(cooler_vars[k] == 0)

        # Cooler TDP must cover CPU TDP (with 20% headroom)
        if tdp_rating > 0:
            for c in range(len(cpu_df)):
                cpu_tdp = get_watts(cpu_df.loc[c].get("TDP", cpu_df.loc[c].get("tdp", 65)), 65)
                if tdp_rating < int(cpu_tdp * 1.2):
                    model.Add(cpu_vars[c] + cooler_vars[k] <= 1)

    return model
