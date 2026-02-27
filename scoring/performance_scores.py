"""
Performance scoring functions.
CPU scoring uses the original formula (cache, boost, lithography, SMT, X3D, price efficiency).
GPU scoring uses original formula (vram × boost_clock).
Both are extended with use-case awareness.
"""
import math
from utils.helpers import extract_number

SCORE_SCALE = 1  # scores are already reasonable integers after rounding


# ═════════════════════════════════════════════════════════════════
# CPU SCORING  (original formula preserved + use-case extension)
# ═════════════════════════════════════════════════════════════════

def cpu_gaming_score(i, cpu_df, budget) -> float:
    """Original CPU gaming score from xo-receng."""
    name   = str(cpu_df.loc[i, "Name"]).lower()
    price  = cpu_df.loc[i, "price"]

    l3     = extract_number(cpu_df.loc[i].get("L3 Cache", 0))
    boost  = extract_number(cpu_df.loc[i].get("Performance Core Boost Clock", 0))
    litho  = extract_number(cpu_df.loc[i].get("Lithography", 10))
    smt    = cpu_df.loc[i].get("Simultaneous Multithreading", False)
    cores  = extract_number(cpu_df.loc[i].get("Core Count", 4))

    # Core gaming traits
    cache_score = math.log1p(l3) * 32
    boost_score = boost * 22
    core_score  = 8 * 2.5 + max(0, cores - 8) * 0.8

    # Architecture bonus
    if litho <= 5:
        arch_score = 25
    elif litho <= 7:
        arch_score = 18
    else:
        arch_score = 8

    smt_bonus = 8 if smt else 0
    x3d_bonus = 70 if "x3d" in name else 0

    raw = cache_score + boost_score + core_score + arch_score + smt_bonus + x3d_bonus

    # Price efficiency scaling based on budget (original logic)
    if budget <= 150000:
        efficiency = raw / (price ** 0.24)
    elif budget <= 250000:
        efficiency = raw / (price ** 0.18)
    elif budget <= 400000:
        efficiency = raw / (price ** 0.10)
    elif budget <= 600000:
        efficiency = raw / (price ** 0.05)
    else:
        efficiency = raw  # no price penalty at ultra budget

    return efficiency


def cpu_productivity_score(i, cpu_df, budget) -> float:
    """Productivity: cores and cache matter more than single-thread boost."""
    name  = str(cpu_df.loc[i, "Name"]).lower()
    price = cpu_df.loc[i, "price"]

    l3    = extract_number(cpu_df.loc[i].get("L3 Cache", 0))
    boost = extract_number(cpu_df.loc[i].get("Performance Core Boost Clock", 0))
    litho = extract_number(cpu_df.loc[i].get("Lithography", 10))
    smt   = cpu_df.loc[i].get("Simultaneous Multithreading", False)
    cores = extract_number(cpu_df.loc[i].get("Core Count", 4))

    cache_score = math.log1p(l3) * 20
    boost_score = boost * 10
    core_score  = cores * 8          # linear core scaling
    arch_score  = 25 if litho <= 5 else (18 if litho <= 7 else 8)
    smt_bonus   = 20 if smt else 0   # SMT matters a lot for productivity

    raw = cache_score + boost_score + core_score + arch_score + smt_bonus

    if budget <= 400000:
        efficiency = raw / (price ** 0.15)
    else:
        efficiency = raw

    return efficiency


def cpu_content_score(i, cpu_df, budget) -> float:
    """Content creation: balanced — needs both cores and clock speed."""
    name  = str(cpu_df.loc[i, "Name"]).lower()
    price = cpu_df.loc[i, "price"]

    l3    = extract_number(cpu_df.loc[i].get("L3 Cache", 0))
    boost = extract_number(cpu_df.loc[i].get("Performance Core Boost Clock", 0))
    litho = extract_number(cpu_df.loc[i].get("Lithography", 10))
    smt   = cpu_df.loc[i].get("Simultaneous Multithreading", False)
    cores = extract_number(cpu_df.loc[i].get("Core Count", 4))

    cache_score = math.log1p(l3) * 25
    boost_score = boost * 16
    core_score  = cores * 5 + max(0, cores - 8) * 3
    arch_score  = 25 if litho <= 5 else (18 if litho <= 7 else 8)
    smt_bonus   = 12 if smt else 0

    raw = cache_score + boost_score + core_score + arch_score + smt_bonus

    if budget <= 400000:
        efficiency = raw / (price ** 0.12)
    else:
        efficiency = raw

    return efficiency


def cpu_score(i, cpu_df, budget, use_case="gaming") -> float:
    """Route to correct CPU scorer by use case."""
    if use_case == "productivity":
        return cpu_productivity_score(i, cpu_df, budget)
    elif use_case == "content_creation":
        return cpu_content_score(i, cpu_df, budget)
    return cpu_gaming_score(i, cpu_df, budget)


# ═════════════════════════════════════════════════════════════════
# GPU SCORING  (original formula preserved + use-case extension)
# ═════════════════════════════════════════════════════════════════

def gpu_gaming_score(i, gpu_df) -> float:
    """Original GPU gaming score: vram × boost_clock."""
    vram       = extract_number(gpu_df.loc[i].get("vram",       gpu_df.loc[i].get("Memory", 8)))
    boost      = extract_number(gpu_df.loc[i].get("boost_clock", gpu_df.loc[i].get("Boost Clock", 1000)))
    return vram * boost


def gpu_productivity_score(i, gpu_df) -> float:
    """Productivity: VRAM matters more (compute/ML workloads)."""
    vram  = extract_number(gpu_df.loc[i].get("vram", gpu_df.loc[i].get("Memory", 8)))
    boost = extract_number(gpu_df.loc[i].get("boost_clock", gpu_df.loc[i].get("Boost Clock", 1000)))
    return (vram ** 1.5) * (boost * 0.5)


def gpu_content_score(i, gpu_df) -> float:
    """Content creation: VRAM + clock both matter (encoding/rendering)."""
    vram  = extract_number(gpu_df.loc[i].get("vram", gpu_df.loc[i].get("Memory", 8)))
    boost = extract_number(gpu_df.loc[i].get("boost_clock", gpu_df.loc[i].get("Boost Clock", 1000)))
    return (vram * 1.2) * boost


def gpu_score(i, gpu_df, use_case="gaming") -> float:
    """Route to correct GPU scorer by use case."""
    if use_case == "productivity":
        return gpu_productivity_score(i, gpu_df)
    elif use_case == "content_creation":
        return gpu_content_score(i, gpu_df)
    return gpu_gaming_score(i, gpu_df)


# ═════════════════════════════════════════════════════════════════
# INTEGER WRAPPERS FOR CP-SAT  (needs integers)
# ═════════════════════════════════════════════════════════════════

def cpu_score_int(i, cpu_df, budget, use_case="gaming") -> int:
    return max(1, int(cpu_score(i, cpu_df, budget, use_case) * 100))

def gpu_score_int(i, gpu_df, use_case="gaming") -> int:
    return max(1, int(gpu_score(i, gpu_df, use_case)))
