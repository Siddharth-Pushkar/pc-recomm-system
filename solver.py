"""
Core CP-SAT solver — 7-component PC Builder
"""
from ortools.sat.python import cp_model
from scoring.performance_scores import cpu_score_int, gpu_score_int
from utils.helpers import get_watts, calculate_psu
from config import USE_CASE_WEIGHTS


class PCSolver:

    def __init__(self, cpu_df, gpu_df, mobo_df, ram_df,
                 storage_df, psu_df, cooler_df,
                 budget, use_case="gaming"):

        self.cpu_df     = cpu_df
        self.gpu_df     = gpu_df
        self.mobo_df    = mobo_df
        self.ram_df     = ram_df
        self.storage_df = storage_df
        self.psu_df     = psu_df
        self.cooler_df  = cooler_df
        self.budget     = budget
        self.use_case   = use_case

        self.model = cp_model.CpModel()

        self.cpu_vars     = [self.model.NewBoolVar(f"cpu_{i}")     for i in range(len(cpu_df))]
        self.gpu_vars     = [self.model.NewBoolVar(f"gpu_{i}")     for i in range(len(gpu_df))]
        self.mobo_vars    = [self.model.NewBoolVar(f"mobo_{i}")    for i in range(len(mobo_df))]
        self.ram_vars     = [self.model.NewBoolVar(f"ram_{i}")     for i in range(len(ram_df))]
        self.storage_vars = [self.model.NewBoolVar(f"storage_{i}") for i in range(len(storage_df))]
        self.psu_vars     = [self.model.NewBoolVar(f"psu_{i}")     for i in range(len(psu_df))]
        self.cooler_vars  = [self.model.NewBoolVar(f"cooler_{i}")  for i in range(len(cooler_df))]

        # CPU generation upgrade constraints applied at init (same as original)
        self._add_cpu_generation_constraints()

    def _add_cpu_generation_constraints(self):
        from utils.helpers import intel_gen, ryzen_gen
        for i in range(len(self.cpu_df)):
            name_i  = str(self.cpu_df.loc[i, "Name"])
            price_i = self.cpu_df.loc[i, "price"]
            ci, gi  = intel_gen(name_i)
            ca, ga  = ryzen_gen(name_i)

            for j in range(len(self.cpu_df)):
                if i == j:
                    continue
                name_j  = str(self.cpu_df.loc[j, "Name"])
                price_j = self.cpu_df.loc[j, "price"]
                cj, gj  = intel_gen(name_j)
                caj, gaj = ryzen_gen(name_j)

                if abs(price_i - price_j) <= 3000:
                    if ci and ci == cj and gi < gj:
                        self.model.Add(self.cpu_vars[i] == 0)
                    if ca and ca == caj and ga < gaj:
                        self.model.Add(self.cpu_vars[i] == 0)

    def add_performance_objective(self):
        cpu_w, gpu_w = USE_CASE_WEIGHTS.get(self.use_case, (0.8, 2.6))
        cpu_w_int = int(cpu_w * 10)
        gpu_w_int = int(gpu_w * 10)

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
                         cpu_df, cpu_vars,
                         gpu_df, gpu_vars,
                         mobo_df, mobo_vars,
                         ram_df, ram_vars,
                         storage_df, storage_vars,
                         psu_df, psu_vars,
                         cooler_df, cooler_vars,
                         budget, use_case, room_condition):

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print("\n❌  No valid build found within constraints and budget.")
            print("    Try increasing your budget or relaxing requirements.")
            return False

        label = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        print(f"\n💻  BEST {use_case.upper().replace('_', ' ')} BUILD ({label}):\n")
        print("─" * 60)

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

        selected_cpu = _pick(cpu_df,     cpu_vars,     "CPU")
        selected_gpu = _pick(gpu_df,     gpu_vars,     "GPU")
        _pick(mobo_df,    mobo_vars,    "Motherboard")
        _pick(ram_df,     ram_vars,     "RAM")
        _pick(storage_df, storage_vars, "Storage")
        _pick(psu_df,     psu_vars,     "PSU")
        _pick(cooler_df,  cooler_vars,  "Cooler")

        print("─" * 60)
        print(f"  {'TOTAL':>52}  ₹{int(total):>8,}")
        print(f"  {'BUDGET':>52}  ₹{int(budget):>8,}")
        print(f"  {'REMAINING':>52}  ₹{int(budget - total):>8,}")

        # PSU sizing guide
        if selected_cpu is not None and selected_gpu is not None:
            cpu_tdp = get_watts(selected_cpu.get("TDP", selected_cpu.get("tdp", 65)), 65)
            gpu_tdp = get_watts(selected_gpu.get("TDP", selected_gpu.get("tdp", 150)), 150)
            psu_w, psu_eff = calculate_psu(cpu_tdp, gpu_tdp, budget)
            print(f"\n📋  PSU Sizing Guide : 80+ {psu_eff} {psu_w}W  "
                  f"(CPU {cpu_tdp}W + GPU {gpu_tdp}W × 2 headroom)")

        dusty = room_condition.strip().lower() in ("yes", "y")
        if dusty:
            print("🌡️   Room Note        : Dusty/warm room — ensure good AIO exhaust, clean filters monthly.")
        print()
        return True
