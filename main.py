"""
PC Build Recommendation System — Entry Point
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import load_and_clean_data
from utils.helpers import calculate_budget_range, get_budget_tier
from solver import PCSolver
from constraints.base_constraints    import add_base_constraints, add_budget_constraint
from constraints.cpu_constraints     import add_cpu_constraints
from constraints.gpu_constraints     import add_gpu_constraints
from constraints.mobo_constraints    import add_mobo_constraints
from constraints.ram_constraints     import add_ram_constraints
from constraints.storage_constraints import add_storage_constraints
from constraints.psu_constraints     import add_psu_constraints
from constraints.cooler_constraints  import add_cooler_constraints

USE_CASES = {"1": "gaming", "2": "productivity", "3": "content_creation"}


def get_inputs():
    print("\n" + "═" * 58)
    print("        🖥️   PC BUILD RECOMMENDATION SYSTEM")
    print("═" * 58)

    while True:
        try:
            budget = int(input("\nEnter total PC budget (₹ INR): ").replace(",", "").strip())
            if budget < 30000:
                print("  ⚠  Minimum budget is ₹30,000.")
                continue
            break
        except ValueError:
            print("  ⚠  Please enter a valid number.")

    print("\nSelect use case:")
    print("  1. Gaming")
    print("  2. Productivity")
    print("  3. Content Creation")
    while True:
        choice = input("Enter choice (1/2/3): ").strip()
        if choice in USE_CASES:
            use_case = USE_CASES[choice]
            break
        print("  ⚠  Enter 1, 2, or 3.")

    room = input("\nIs your room dusty and/or warm? (yes/no): ").strip().lower()
    wifi = input("Do you need onboard WiFi? (yes/no): ").strip().lower()
    require_wifi = wifi in ("yes", "y")

    return budget, use_case, room, require_wifi


def main():
    budget, use_case, room_condition, require_wifi = get_inputs()

    tier  = get_budget_tier(budget)
    lower, upper = calculate_budget_range(budget)

    print(f"\n  Budget tier   : {tier.upper()}")
    print(f"  Use case      : {use_case.replace('_', ' ').title()}")
    print(f"  Budget range  : ₹{lower:,} — ₹{upper:,}")
    print(f"  WiFi required : {'Yes' if require_wifi else 'No'}")
    print(f"\n  Loading data...")

    try:
        cpu_df, gpu_df, mobo_df, ram_df, storage_df, psu_df, cooler_df = load_and_clean_data()
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    print("\n  Building constraint model...")
    pc = PCSolver(cpu_df, gpu_df, mobo_df, ram_df,
                  storage_df, psu_df, cooler_df,
                  budget, use_case)

    add_base_constraints(
        pc.model,
        pc.cpu_vars, pc.gpu_vars, pc.mobo_vars, pc.ram_vars,
        pc.storage_vars, pc.psu_vars, pc.cooler_vars
    )
    add_budget_constraint(
        pc.model,
        cpu_df, gpu_df, mobo_df, ram_df, storage_df, psu_df, cooler_df,
        pc.cpu_vars, pc.gpu_vars, pc.mobo_vars, pc.ram_vars,
        pc.storage_vars, pc.psu_vars, pc.cooler_vars,
        lower, upper
    )
    add_cpu_constraints(
        pc.model, cpu_df, pc.cpu_vars, budget,
        pc.gpu_vars, gpu_df, pc.mobo_vars, mobo_df,
        pc.ram_vars, ram_df, use_case
    )
    add_gpu_constraints(
        pc.model, gpu_df, pc.gpu_vars, budget,
        pc.cpu_vars, cpu_df, use_case
    )
    add_mobo_constraints(
        pc.model, mobo_df, pc.mobo_vars,
        pc.cpu_vars, cpu_df, pc.gpu_vars, gpu_df,
        budget, require_wifi=require_wifi
    )
    add_ram_constraints(pc.model, ram_df, pc.ram_vars, pc.cpu_vars, cpu_df, budget)
    add_storage_constraints(pc.model, storage_df, pc.storage_vars, budget)
    add_psu_constraints(
        pc.model, psu_df, pc.psu_vars,
        cpu_df, pc.cpu_vars, gpu_df, pc.gpu_vars, budget
    )
    add_cooler_constraints(
        pc.model, cooler_df, pc.cooler_vars,
        cpu_df, pc.cpu_vars, budget, room_condition
    )

    pc.add_performance_objective()

    print("  Solving...\n")
    solver, status = pc.solve()

    PCSolver.display_solution(
        status, solver,
        cpu_df,     pc.cpu_vars,
        gpu_df,     pc.gpu_vars,
        mobo_df,    pc.mobo_vars,
        ram_df,     pc.ram_vars,
        storage_df, pc.storage_vars,
        psu_df,     pc.psu_vars,
        cooler_df,  pc.cooler_vars,
        budget, use_case, room_condition
    )


if __name__ == "__main__":
    main()
