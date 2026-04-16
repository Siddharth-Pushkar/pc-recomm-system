"""
Productivity Engine
===================
Self-contained engine for productivity PC builds.
Prioritises core count, SMT, and RAM capacity over gaming clock speed.
No gaming or content creation logic runs here.
"""
from ortools.sat.python import cp_model

from data_loader import load_and_clean_data
from solver import PCSolver
from utils.helpers import calculate_budget_range, get_budget_tier

from constraints.base_constraints import add_base_constraints, add_budget_constraint
from constraints.cpu_constraints  import add_cpu_constraints
from constraints.gpu_constraints  import add_gpu_constraints
from constraints.mobo_constraints import add_mobo_constraints
from constraints.ram_constraints  import add_ram_constraints


def run_productivity_engine(budget: int, require_wifi: bool = False):
    """
    Run the productivity recommendation engine.

    Parameters
    ----------
    budget       : total build budget in INR
    require_wifi : whether the user needs onboard WiFi
    """

    tier         = get_budget_tier(budget)
    lower, upper = calculate_budget_range(budget)

    print(f"\n  Budget tier   : {tier.upper()}")
    print(f"  Use case      : PRODUCTIVITY")
    print(f"  Budget range  : ₹{lower:,} — ₹{upper:,}")
    print(f"  WiFi required : {'Yes' if require_wifi else 'No'}")
    print(f"\n  Loading data...")

    cpu_df, gpu_df, mobo_df, ram_df = load_and_clean_data()

    print("\n  Building constraint model...")

    pc = PCSolver(cpu_df, gpu_df, mobo_df, ram_df,
                  budget, use_case="productivity")

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

    # ── Productivity-specific component constraints ───────────────
    # CPU: use_case="productivity" enforces 8-core minimum in add_cpu_constraints
    add_cpu_constraints(
        pc.model, cpu_df, pc.cpu_vars, budget,
        pc.gpu_vars, gpu_df,
        pc.mobo_vars, mobo_df,
        pc.ram_vars, ram_df,
        use_case="productivity"
    )
    add_gpu_constraints(
        pc.model, gpu_df, pc.gpu_vars, budget,
        pc.cpu_vars, cpu_df,
        use_case="productivity"
    )
    add_mobo_constraints(
        pc.model, mobo_df, pc.mobo_vars,
        pc.cpu_vars, cpu_df,
        pc.gpu_vars, gpu_df,
        budget, require_wifi=require_wifi
    )

    # RAM: productivity builds push toward higher capacity
    # 32 GB enforced via budget > 200000 rule in add_ram_constraints
    add_ram_constraints(
        pc.model, ram_df, pc.ram_vars,
        pc.cpu_vars, cpu_df,
        budget
    )

    # ── Maximise productivity performance score ───────────────────
    pc.add_performance_objective()

    print("  Solving...\n")
    solver, status = pc.solve()

    PCSolver.display_solution(
        status, solver,
        cpu_df,  pc.cpu_vars,
        gpu_df,  pc.gpu_vars,
        mobo_df, pc.mobo_vars,
        ram_df,  pc.ram_vars,
        budget, use_case="productivity"
    )
