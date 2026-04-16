"""
Gaming Engine
=============
Self-contained engine for gaming PC builds.
Only loads and applies constraints relevant to gaming.
No content creation or productivity logic runs here.
"""
from ortools.sat.python import cp_model

from data_loader import load_and_clean_data
from solver import PCSolver, suggest_psu, suggest_storage
from utils.helpers import calculate_budget_range, get_budget_tier

from constraints.base_constraints import add_base_constraints, add_budget_constraint
from constraints.cpu_constraints  import add_cpu_constraints
from constraints.gpu_constraints  import add_gpu_constraints
from constraints.mobo_constraints import add_mobo_constraints
from constraints.ram_constraints  import add_ram_constraints


def run_gaming_engine(budget: int, require_wifi: bool = False):
    """
    Run the gaming recommendation engine.

    Parameters
    ----------
    budget       : total build budget in INR
    require_wifi : whether the user needs onboard WiFi
    """

    tier         = get_budget_tier(budget)
    lower, upper = calculate_budget_range(budget)

    print(f"\n  Budget tier   : {tier.upper()}")
    print(f"  Use case      : GAMING")
    print(f"  Budget range  : ₹{lower:,} — ₹{upper:,}")
    print(f"  WiFi required : {'Yes' if require_wifi else 'No'}")
    print(f"\n  Loading data...")

    cpu_df, gpu_df, mobo_df, ram_df = load_and_clean_data()

    print("\n  Building constraint model...")

    pc = PCSolver(cpu_df, gpu_df, mobo_df, ram_df,
                  budget, use_case="gaming")

    # ── Exactly one per category ──────────────────────────────────
    add_base_constraints(
        pc.model,
        pc.cpu_vars, pc.gpu_vars, pc.mobo_vars, pc.ram_vars
    )

    # ── Total cost within budget range ───────────────────────────
    add_budget_constraint(
        pc.model,
        cpu_df, gpu_df, mobo_df, ram_df,
        pc.cpu_vars, pc.gpu_vars, pc.mobo_vars, pc.ram_vars,
        lower, upper
    )

    # ── Gaming-specific component constraints ─────────────────────
    add_cpu_constraints(
        pc.model, cpu_df, pc.cpu_vars, budget,
        pc.gpu_vars, gpu_df,
        pc.mobo_vars, mobo_df,
        pc.ram_vars, ram_df,
        use_case="gaming"
    )
    add_gpu_constraints(
        pc.model, gpu_df, pc.gpu_vars, budget,
        pc.cpu_vars, cpu_df,
        use_case="gaming"
    )
    add_mobo_constraints(
        pc.model, mobo_df, pc.mobo_vars,
        pc.cpu_vars, cpu_df,
        pc.gpu_vars, gpu_df,
        budget, require_wifi=require_wifi
    )
    add_ram_constraints(
        pc.model, ram_df, pc.ram_vars,
        pc.cpu_vars, cpu_df,
        budget
    )

    # ── Maximise gaming performance score ────────────────────────
    pc.add_performance_objective()

    print("  Solving...\n")
    solver, status = pc.solve()

    PCSolver.display_solution(
        status, solver,
        cpu_df,  pc.cpu_vars,
        gpu_df,  pc.gpu_vars,
        mobo_df, pc.mobo_vars,
        ram_df,  pc.ram_vars,
        budget, use_case="gaming"
    )
