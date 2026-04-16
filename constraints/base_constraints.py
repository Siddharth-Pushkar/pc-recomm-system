"""
Base constraints: exactly-one selection per category + total budget range
4 components only: CPU, GPU, MOBO, RAM
"""

def add_base_constraints(model, cpu_vars, gpu_vars, mobo_vars, ram_vars):
    model.Add(sum(cpu_vars)  == 1)
    model.Add(sum(gpu_vars)  == 1)
    model.Add(sum(mobo_vars) == 1)
    model.Add(sum(ram_vars)  == 1)
    return model


def add_budget_constraint(model,
                          cpu_df, gpu_df, mobo_df, ram_df,
                          cpu_vars, gpu_vars, mobo_vars, ram_vars,
                          lower_limit, upper_limit):
    total_cost = (
        sum(int(cpu_df.loc[i,  "price"]) * cpu_vars[i]  for i in range(len(cpu_df)))  +
        sum(int(gpu_df.loc[i,  "price"]) * gpu_vars[i]  for i in range(len(gpu_df)))  +
        sum(int(mobo_df.loc[i, "price"]) * mobo_vars[i] for i in range(len(mobo_df))) +
        sum(int(ram_df.loc[i,  "price"]) * ram_vars[i]  for i in range(len(ram_df)))
    )
    model.Add(total_cost >= lower_limit)
    model.Add(total_cost <= upper_limit)
    return model
