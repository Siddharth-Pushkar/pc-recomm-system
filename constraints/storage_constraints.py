"""
Storage constraints — NVMe preference, capacity scaling by budget
"""
from utils.helpers import get_storage_capacity_gb, is_nvme


def add_storage_constraints(model, storage_df, storage_vars, budget):

    for s in range(len(storage_df)):
        name     = str(storage_df.loc[s, "Name"])
        capacity = get_storage_capacity_gb(name)
        nvme     = is_nvme(name)

        if budget < 100000:
            if capacity < 512:
                model.Add(storage_vars[s] == 0)

        elif budget < 300000:
            if capacity < 1024:
                model.Add(storage_vars[s] == 0)
            if not nvme:
                model.Add(storage_vars[s] == 0)

        elif budget < 700000:
            if not nvme:
                model.Add(storage_vars[s] == 0)
            if capacity < 1024:
                model.Add(storage_vars[s] == 0)

        else:  # ultra
            if not nvme:
                model.Add(storage_vars[s] == 0)
            if capacity < 2048:
                model.Add(storage_vars[s] == 0)

    return model
