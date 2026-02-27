"""
PSU constraints — efficiency floor + wattage range by budget tier
"""
from utils.helpers import get_watts, get_budget_tier


EFFICIENCY_RANK = {"White": 0, "Bronze": 1, "Silver": 2, "Gold": 3, "Platinum": 4, "Titanium": 5}

EFFICIENCY_FLOOR = {
    "entry": "Bronze",
    "low":   "Bronze",
    "mid":   "Gold",
    "high":  "Platinum",
    "ultra": "Platinum",
}

WATT_FLOOR = {"entry": 450, "low": 550, "mid": 650, "high": 750, "ultra": 850}
WATT_CEIL  = {"entry": 650, "low": 750, "mid": 850, "high": 1200, "ultra": 1600}


def add_psu_constraints(model, psu_df, psu_vars,
                        cpu_df, cpu_vars, gpu_df, gpu_vars, budget):

    tier        = get_budget_tier(budget)
    floor_rank  = EFFICIENCY_RANK.get(EFFICIENCY_FLOOR.get(tier, "Bronze"), 1)
    min_watts   = WATT_FLOOR.get(tier, 450)
    max_watts   = WATT_CEIL.get(tier, 850)

    for p in range(len(psu_df)):
        rating = str(psu_df.loc[p].get("Efficiency", psu_df.loc[p].get("Rating", "Bronze")))
        psu_rank = 0
        for label, rank in EFFICIENCY_RANK.items():
            if label.lower() in rating.lower():
                psu_rank = rank
                break

        if psu_rank < floor_rank:
            model.Add(psu_vars[p] == 0)

        watts = get_watts(psu_df.loc[p].get("Wattage", psu_df.loc[p].get("Power", 0)), 0)

        if watts > 0 and watts < min_watts:
            model.Add(psu_vars[p] == 0)
        if watts > max_watts:
            model.Add(psu_vars[p] == 0)

    return model
