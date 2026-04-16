"""
Core CP-SAT solver — 4-component PC Builder (CPU, GPU, MOBO, RAM)
PSU is calculated via formula and displayed — no dataset or vars needed.
Storage is suggested via budget tier — no dataset or vars needed.
"""
from ortools.sat.python import cp_model
from scoring.performance_scores import cpu_score_int, gpu_score_int
from utils.helpers import get_watts, get_budget_tier
from config import USE_CASE_WEIGHTS, PSU_SIZES


# ── PSU formula ──────────────────────────────────────────────────────────────
def _next_psu_tier(watts: int) -> int:
    for tier in sorted(PSU_SIZES):
        if tier >= watts:
            return tier
    return PSU_SIZES[-1]


def suggest_psu(cpu_tdp: int, gpu_tdp: int, budget: int) -> tuple:
    """
    Returns (wattage, efficiency_label).
    Formula: (cpu_tdp + gpu_tdp) × 2, rounded up to next standard tier.
    """
    recommended = (cpu_tdp + gpu_tdp) * 2
    wattage     = _next_psu_tier(recommended)

    if budget < 130000:
        efficiency = "Bronze"
    elif budget < 250000:
        efficiency = "Gold"
    elif budget < 500000:
        efficiency = "Gold"
    else:
        efficiency = "Platinum"

    return wattage, efficiency


# ── Storage suggestion ────────────────────────────────────────────────────────
def suggest_storage(budget: int) -> str:
    tier = get_budget_tier(budget)
    if tier == "entry":
        return "512GB NVMe SSD"
    elif tier == "low":
        return "1TB NVMe SSD"
    elif tier == "mid":
        return "1TB NVMe SSD  +  1TB HDD (or 2TB NVMe)"
    elif tier == "high":
        return "2TB NVMe SSD  +  2TB HDD"
    else:
        return "2TB NVMe Gen4/5 SSD  +  4TB HDD"


# ── Solver ────────────────────────────────────────────────────────────────────
class PCSolver:

    def __init__(self, cpu_df, gpu_df, mobo_df, ram_df,
                 budget, use_case="gaming"):

        self.cpu_df   = cpu_df
        self.gpu_df   = gpu_df
        self.mobo_df  = mobo_df
        self.ram_df   = ram_df
        self.budget   = budget
        self.use_case = use_case

        self.model = cp_model.CpModel()

        self.cpu_vars  = [self.model.NewBoolVar(f"cpu_{i}")  for i in range(len(cpu_df))]
        self.gpu_vars  = [self.model.NewBoolVar(f"gpu_{i}")  for i in range(len(gpu_df))]
        self.mobo_vars = [self.model.NewBoolVar(f"mobo_{i}") for i in range(len(mobo_df))]
        self.ram_vars  = [self.model.NewBoolVar(f"ram_{i}")  for i in range(len(ram_df))]

    def add_performance_objective(self):
        cpu_w, gpu_w = USE_CASE_WEIGHTS.get(self.use_case, (0.8, 2.6))
        cpu_w_int    = int(cpu_w * 10)
        gpu_w_int    = int(gpu_w * 10)

        performance = (
            sum(cpu_score_int(i, self.cpu_df, self.budget, self.use_case) * cpu_w_int * self.cpu_vars[i]
                for i in range(len(self.cpu_df))) +
            sum(gpu_score_int(i, self.gpu_df, self.use_case) * gpu_w_int * self.gpu_vars[i]
                for i in range(len(self.gpu_df)))
        )
        self.model.Maximize(performance)

    def solve(self):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(self.model)
        return solver, status

    @staticmethod
    def display_solution(status, solver,
                         cpu_df,  cpu_vars,
                         gpu_df,  gpu_vars,
                         mobo_df, mobo_vars,
                         ram_df,  ram_vars,
                         budget, use_case):

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print("\n❌  No valid build found within constraints and budget.")
            print("    Try increasing your budget or relaxing requirements.")
            return False

        label = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        print(f"\n💻  BEST {use_case.upper().replace('_', ' ')} BUILD ({label}):\n")
        print("─" * 62)

        total        = 0
        selected_cpu = None
        selected_gpu = None

        def _pick(df, var_list, label_str):
            nonlocal total
            for i in range(len(df)):
                if solver.Value(var_list[i]):
                    price = df.loc[i, "price"]
                    total += price
                    print(f"  {label_str:<14} {str(df.loc[i, 'Name']):<38}  ₹{int(price):>8,}")
                    return df.loc[i]
            return None

        selected_cpu = _pick(cpu_df,  cpu_vars,  "CPU")
        selected_gpu = _pick(gpu_df,  gpu_vars,  "GPU")
        _pick(mobo_df, mobo_vars, "Motherboard")
        _pick(ram_df,  ram_vars,  "RAM")

        print("─" * 62)
        print(f"  {'TOTAL':>52}  ₹{int(total):>8,}")
        print(f"  {'BUDGET':>52}  ₹{int(budget):>8,}")
        print(f"  {'REMAINING':>52}  ₹{int(budget - total):>8,}")

        # PSU recommendation (formula only — no dataset)
        if selected_cpu is not None and selected_gpu is not None:
            cpu_tdp = get_watts(selected_cpu.get("TDP", 65), 65)
            gpu_tdp = get_watts(selected_gpu.get("TDP", 150), 150)
            psu_w, psu_eff = suggest_psu(cpu_tdp, gpu_tdp, budget)
            print(f"\n📋  Recommended PSU    : 80+ {psu_eff} {psu_w}W"
                  f"  (CPU {cpu_tdp}W + GPU {gpu_tdp}W × 2)")

        # Storage suggestion (budget-tier based — no dataset)
        storage_suggestion = suggest_storage(budget)
        print(f"💾  Suggested Storage  : {storage_suggestion}")
        print()

        return True
