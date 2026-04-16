"""
Content Creation Engine
=======================
Self-contained engine for content creator PC builds.
Supports sub-categories: video_editing, rendering_3d, motion_graphics,
ai_ml, photo_editing, music_production.
No gaming or productivity logic runs here.
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


# ── Sub-category constraint functions ────────────────────────────────────────
# Each function applies only the rules relevant to that workload.
# All are independent — no shared state, no cross-category pollution.

import re
from utils.helpers import get_int, get_budget_tier as _tier


def _get_vram(gpu_row) -> int:
    from utils.helpers import extract_number
    return int(extract_number(gpu_row.get("Memory", gpu_row.get("vram", 4))) or 4)


def _get_cores(cpu_row) -> int:
    from utils.helpers import extract_number
    return int(extract_number(cpu_row.get("Core Count", 4)) or 4)


def _is_nvidia(gpu_row) -> bool:
    name = str(gpu_row.get("Name", gpu_row.get("name", ""))).lower()
    return any(x in name for x in ["rtx", "gtx", "geforce"])


def _parse_total_gb(modules_str: str) -> int:
    s = str(modules_str).replace(" ", "").upper()
    m = re.match(r"(\d+)X(\d+)GB", s)
    if m:
        return int(m.group(1)) * int(m.group(2))
    m2 = re.search(r"(\d+)GB", s)
    return int(m2.group(1)) if m2 else 0


def _get_boost(cpu_row) -> float:
    from utils.helpers import extract_number
    for col in ("Performance Core Boost Clock", "boost_clock", "Boost Clock"):
        if col in cpu_row.index:
            v = extract_number(cpu_row[col])
            if v > 0:
                return float(v)
    return 0.0


def _apply_video_editing(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                         ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    Video Editing (Premiere, DaVinci Resolve, Final Cut)

    VRAM floors by tier:
      entry/low  → 4 GB min (best available, no hard block)
      mid        → 8 GB min
      high/ultra → 12 GB min

    NVIDIA preference: mid+ only (CUDA for DaVinci)
    RAM floors: entry/low → 16 GB, mid → 32 GB, high/ultra → 64 GB
    M.2 slots ≥ 2: mid+ only
    """
    from utils.helpers import get_m2_slots

    for g in range(len(gpu_df)):
        vram = _get_vram(gpu_df.loc[g])
        if tier == "mid" and vram > 0 and vram < 8:
            model.Add(gpu_vars[g] == 0)
        if tier in ("high", "ultra") and vram > 0 and vram < 12:
            model.Add(gpu_vars[g] == 0)
        if tier in ("mid", "high", "ultra") and not _is_nvidia(gpu_df.loc[g]):
            model.Add(gpu_vars[g] == 0)

    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if tier in ("mid",) and total_gb > 0 and total_gb < 32:
            model.Add(ram_vars[r] == 0)
        if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
            model.Add(ram_vars[r] == 0)

    if tier in ("mid", "high", "ultra"):
        for m in range(len(mobo_df)):
            m2 = get_m2_slots(mobo_df.loc[m])
            if m2 > 0 and m2 < 2:
                model.Add(mobo_vars[m] == 0)


def _apply_rendering_3d(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                        ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    3D Rendering (Blender, Cinema 4D, Houdini)

    Core count floors by tier:
      entry/low  → 6 cores min
      mid        → 8 cores min
      high/ultra → 12 cores min

    GPU VRAM floors:
      mid        → 8 GB min
      high/ultra → 16 GB min

    RAM: mid → 32 GB, high/ultra → 64 GB
    """
    CORE_FLOORS = {"entry": 6, "low": 6, "mid": 8, "high": 12, "ultra": 12}
    min_cores = CORE_FLOORS.get(tier, 6)
    for c in range(len(cpu_df)):
        cores = _get_cores(cpu_df.loc[c])
        if cores > 0 and cores < min_cores:
            model.Add(cpu_vars[c] == 0)

    for g in range(len(gpu_df)):
        vram = _get_vram(gpu_df.loc[g])
        if tier == "mid" and vram > 0 and vram < 8:
            model.Add(gpu_vars[g] == 0)
        if tier in ("high", "ultra") and vram > 0 and vram < 16:
            model.Add(gpu_vars[g] == 0)

    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if tier in ("mid",) and total_gb > 0 and total_gb < 32:
            model.Add(ram_vars[r] == 0)
        if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
            model.Add(ram_vars[r] == 0)


def _apply_motion_graphics(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                            ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    Motion Graphics & VFX (After Effects, DaVinci Fusion)

    RAM floors:
      entry/low  → 16 GB (best available)
      mid        → 32 GB
      high/ultra → 64 GB (AE caches entire comp frames in RAM)

    GPU VRAM ≥ 8 GB at mid+, ≥ 12 GB at high/ultra
    """
    RAM_FLOORS = {"entry": 0, "low": 0, "mid": 32, "high": 64, "ultra": 64}
    min_ram = RAM_FLOORS.get(tier, 0)
    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if min_ram > 0 and total_gb > 0 and total_gb < min_ram:
            model.Add(ram_vars[r] == 0)

    for g in range(len(gpu_df)):
        vram = _get_vram(gpu_df.loc[g])
        if tier == "mid" and vram > 0 and vram < 8:
            model.Add(gpu_vars[g] == 0)
        if tier in ("high", "ultra") and vram > 0 and vram < 12:
            model.Add(gpu_vars[g] == 0)


def _apply_ai_ml(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                 ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    AI / ML (Stable Diffusion, LoRA training, inference)

    VRAM floors by tier:
      entry/low  → 8 GB min
      mid        → 12 GB min
      high/ultra → 16 GB min

    NVIDIA preferred: mid+ only
    RAM: mid → 32 GB, high/ultra → 64 GB
    PCIe 5.0: high/ultra only
    """
    from utils.helpers import get_pcie_version

    VRAM_FLOORS = {"entry": 8, "low": 8, "mid": 12, "high": 16, "ultra": 16}
    min_vram = VRAM_FLOORS.get(tier, 8)

    for g in range(len(gpu_df)):
        vram = _get_vram(gpu_df.loc[g])
        if vram > 0 and vram < min_vram:
            model.Add(gpu_vars[g] == 0)
        if tier in ("mid", "high", "ultra") and not _is_nvidia(gpu_df.loc[g]):
            model.Add(gpu_vars[g] == 0)

    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if tier in ("mid",) and total_gb > 0 and total_gb < 32:
            model.Add(ram_vars[r] == 0)
        if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
            model.Add(ram_vars[r] == 0)

    if tier in ("high", "ultra"):
        for m in range(len(mobo_df)):
            pcie = get_pcie_version(mobo_df.loc[m])
            if pcie > 0 and pcie < 5:
                model.Add(mobo_vars[m] == 0)


def _apply_photo_editing(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                         ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    Photo Editing & Batch Processing (Lightroom, Photoshop)

    Boost clock floors:
      low        → 3.8 GHz min
      mid+       → 4.5 GHz min

    RAM: low → 16 GB, mid+ → 32 GB
    M.2 slots ≥ 2: mid+ only
    """
    from utils.helpers import get_m2_slots

    BOOST_FLOORS = {"low": 3.8, "mid": 4.5, "high": 4.5, "ultra": 4.5}
    min_boost = BOOST_FLOORS.get(tier, 0.0)
    if min_boost > 0:
        for c in range(len(cpu_df)):
            boost = _get_boost(cpu_df.loc[c])
            if boost > 0 and boost < min_boost:
                model.Add(cpu_vars[c] == 0)

    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if tier in ("mid", "high", "ultra") and total_gb > 0 and total_gb < 32:
            model.Add(ram_vars[r] == 0)

    if tier in ("mid", "high", "ultra"):
        for m in range(len(mobo_df)):
            m2 = get_m2_slots(mobo_df.loc[m])
            if m2 > 0 and m2 < 2:
                model.Add(mobo_vars[m] == 0)


def _apply_music_production(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                             ram_df, ram_vars, mobo_df, mobo_vars, tier):
    """
    Music Production / DAW (FL Studio, Ableton, Logic)

    Boost clock floors:
      low        → 4.0 GHz min
      mid+       → 4.8 GHz min

    RAM: mid+ → 32 GB
    USB count ≥ 6: mid+ only
    GPU: no constraint — budget reallocated to CPU/RAM
    """
    from utils.helpers import get_usb_count

    BOOST_FLOORS = {"low": 4.0, "mid": 4.8, "high": 4.8, "ultra": 4.8}
    min_boost = BOOST_FLOORS.get(tier, 0.0)
    if min_boost > 0:
        for c in range(len(cpu_df)):
            boost = _get_boost(cpu_df.loc[c])
            if boost > 0 and boost < min_boost:
                model.Add(cpu_vars[c] == 0)

    for r in range(len(ram_df)):
        total_gb = _parse_total_gb(ram_df.loc[r].get("Modules", ""))
        if tier in ("mid", "high", "ultra") and total_gb > 0 and total_gb < 32:
            model.Add(ram_vars[r] == 0)

    if tier in ("mid", "high", "ultra"):
        for m in range(len(mobo_df)):
            usb = get_usb_count(mobo_df.loc[m])
            if usb > 0 and usb < 6:
                model.Add(mobo_vars[m] == 0)


# ── Sub-category router ───────────────────────────────────────────────────────
_SUB_CAT_MAP = {
    "video_editing":   _apply_video_editing,
    "rendering_3d":    _apply_rendering_3d,
    "motion_graphics": _apply_motion_graphics,
    "ai_ml":           _apply_ai_ml,
    "photo_editing":   _apply_photo_editing,
    "music_production":_apply_music_production,
}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def run_content_engine(budget: int, sub_category: str = None,
                       require_wifi: bool = False):
    """
    Run the content creation recommendation engine.

    Parameters
    ----------
    budget       : total build budget in INR
    sub_category : "video_editing" | "rendering_3d" | "motion_graphics" |
                   "ai_ml" | "photo_editing" | "music_production" | None
    require_wifi : whether the user needs onboard WiFi
    """

    tier         = get_budget_tier(budget)
    lower, upper = calculate_budget_range(budget)

    print(f"\n  Budget tier   : {tier.upper()}")
    print(f"  Use case      : CONTENT CREATION")
    if sub_category:
        print(f"  Sub-category  : {sub_category.replace('_', ' ').title()}")
    print(f"  Budget range  : ₹{lower:,} — ₹{upper:,}")
    print(f"  WiFi required : {'Yes' if require_wifi else 'No'}")
    print(f"\n  Loading data...")

    cpu_df, gpu_df, mobo_df, ram_df = load_and_clean_data()

    print("\n  Building constraint model...")

    pc = PCSolver(cpu_df, gpu_df, mobo_df, ram_df,
                  budget, use_case="content_creation")

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

    # ── Base content creation constraints ─────────────────────────
    # use_case="content_creation" enforces 6-core minimum in CPU constraints
    add_cpu_constraints(
        pc.model, cpu_df, pc.cpu_vars, budget,
        pc.gpu_vars, gpu_df,
        pc.mobo_vars, mobo_df,
        pc.ram_vars, ram_df,
        use_case="content_creation"
    )
    add_gpu_constraints(
        pc.model, gpu_df, pc.gpu_vars, budget,
        pc.cpu_vars, cpu_df,
        use_case="content_creation"
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

    # ── Sub-category specific constraints ─────────────────────────
    # Only the rules for the chosen workload are applied.
    # If no sub_category given, base CC constraints are sufficient.
    if sub_category and sub_category in _SUB_CAT_MAP:
        _SUB_CAT_MAP[sub_category](
            pc.model,
            cpu_df, pc.cpu_vars,
            gpu_df, pc.gpu_vars,
            ram_df, pc.ram_vars,
            mobo_df, pc.mobo_vars,
            tier
        )

    # ── Maximise content creation performance score ───────────────
    pc.add_performance_objective()

    print("  Solving...\n")
    solver, status = pc.solve()

    PCSolver.display_solution(
        status, solver,
        cpu_df,  pc.cpu_vars,
        gpu_df,  pc.gpu_vars,
        mobo_df, pc.mobo_vars,
        ram_df,  pc.ram_vars,
        budget, use_case="content_creation"
    )
