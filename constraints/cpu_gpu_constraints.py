"""
CPU ↔ GPU Pair Constraints
===========================
Covers:
  - Base pairing rules (core count floors, no weak CPU + strong GPU)
  - Content creator use-case rules (rendering, AI/ML, VRAM floors)
  - Bottleneck prevention scoring penalties

Doc ref: "CPU ↔ GPU PAIR CONSTRAINTS"
"""
from utils.helpers import get_int, get_watts, extract_gpu_tier, get_budget_tier


# ── Tier helpers ────────────────────────────────────────────────────────────

ENTRY_CPU_SERIES = ["core i3", "ryzen 3"]

MID_HIGH_GPU_KEYWORDS = [
    "rtx 4070", "rtx 4080", "rtx 4090",
    "rtx 5070", "rtx 5080", "rtx 5090",
    "rx 7800", "rx 7900", "rx 9070", "rx 9060",
]

def _is_entry_cpu(cpu_name: str) -> bool:
    name = cpu_name.lower()
    return any(s in name for s in ENTRY_CPU_SERIES)

def _is_mid_high_gpu(gpu_name: str) -> bool:
    name = gpu_name.lower()
    return any(k in name for k in MID_HIGH_GPU_KEYWORDS)

def _get_vram_gb(gpu_row) -> int:
    """Extract VRAM in GB from gpu['Memory'] e.g. '16 GB' → 16"""
    # [GPU: Memory]
    val = str(gpu_row.get("Memory", gpu_row.get("memory", "0")))
    import re
    m = re.search(r"(\d+)", val)
    return int(m.group(1)) if m else 0

def _get_core_count(cpu_row) -> int:
    # [CPU: Core Count]
    return get_int(cpu_row.get("Core Count", cpu_row.get("core_count", 0)), 0)

def _has_smt(cpu_row) -> bool:
    # [CPU: Simultaneous Multithreading]
    val = str(cpu_row.get("Simultaneous Multithreading", "")).lower()
    return "yes" in val or "hyper" in val

def _is_nvidia(gpu_name: str) -> bool:
    return "rtx" in gpu_name.lower() or "gtx" in gpu_name.lower() or "geforce" in gpu_name.lower()

def _get_gpu_vram_from_chipset(gpu_row) -> int:
    """Prefer Memory col, fallback to parsing Chipset name."""
    vram = _get_vram_gb(gpu_row)
    if vram == 0:
        chipset = str(gpu_row.get("Chipset", ""))
        import re
        m = re.search(r"(\d+)\s*gb", chipset.lower())
        vram = int(m.group(1)) if m else 0
    return vram


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONSTRAINT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def add_cpu_gpu_constraints(model, cpu_df, cpu_vars, gpu_df, gpu_vars,
                            budget: int, use_case: str = "gaming"):
    """
    Apply CPU ↔ GPU pairing constraints.

    Parameters
    ----------
    model      : CP-SAT CpModel
    cpu_df     : cleaned CPU dataframe
    cpu_vars   : list of BoolVar, one per CPU row
    gpu_df     : cleaned GPU dataframe
    gpu_vars   : list of BoolVar, one per GPU row
    budget     : total build budget in INR
    use_case   : "gaming" | "productivity" | "content_creation"
    """

    tier = get_budget_tier(budget)
    is_cc = (use_case == "content_creation")

    for c in range(len(cpu_df)):
        cpu_row  = cpu_df.loc[c]
        cpu_name = str(cpu_row.get("Name", cpu_row.get("name", "")))
        cores    = _get_core_count(cpu_row)
        has_smt  = _has_smt(cpu_row)

        for g in range(len(gpu_df)):
            gpu_row  = gpu_df.loc[g]
            gpu_name = str(gpu_row.get("Name", gpu_row.get("name", "")))
            vram     = _get_vram_gb(gpu_row)

            # ── BASE RULE 1 ───────────────────────────────────────────────
            # CPU core count < 8 cannot be paired with any GPU in this system.
            # A sub-8-core CPU starves render pipelines regardless of GPU tier.
            # [CPU: Core Count]
            if cores > 0 and cores < 8:
                model.Add(cpu_vars[c] == 0)
                break  # no need to check GPU pairs for this CPU

            # ── BASE RULE 2 ───────────────────────────────────────────────
            # Entry-tier CPU (i3 / Ryzen 3) must not pair with mid-high GPU.
            # A ₹10k CPU bottlenecking a ₹60k+ GPU wastes the build budget.
            # [CPU: Series] [GPU: Chipset]
            if _is_entry_cpu(cpu_name) and _is_mid_high_gpu(gpu_name):
                model.Add(cpu_vars[c] + gpu_vars[g] <= 1)

            # ── CONTENT CREATOR RULES ─────────────────────────────────────

            if is_cc:

                # CC RULE 1 — 3D rendering: CPU core count ≥ 12
                # Render time scales linearly with cores; below 12 is a bottleneck.
                # Enforced as a hard floor only for mid/high/ultra budget tiers
                # where a 12-core CPU is reachable within budget.
                # [CPU: Core Count]
                if tier in ("mid", "high", "ultra") and cores > 0 and cores < 12:
                    model.Add(cpu_vars[c] == 0)
                    break

                # CC RULE 2 — AI/ML: VRAM ≥ 16 GB must pair with CPU ≥ 8 cores
                # Large VRAM GPUs used for inference/training need a capable
                # CPU to manage data pipeline and preprocessing.
                # [GPU: Memory] [CPU: Core Count]
                if vram >= 16 and cores > 0 and cores < 8:
                    model.Add(cpu_vars[c] + gpu_vars[g] <= 1)

                # CC RULE 3 — 4K video editing VRAM floor: GPU must have ≥ 12 GB
                # Frame buffers for full-res 4K timeline playback live in VRAM.
                # Entry GPUs with 6–8 GB cause constant proxy fallback.
                # [GPU: Memory]
                if tier in ("mid", "high", "ultra") and vram > 0 and vram < 12:
                    model.Add(gpu_vars[g] == 0)

                # CC RULE 4 — High-core CPU preference for rendering
                # Ryzen 9 / Core i9 series have large L3 cache which reduces
                # texture fetch stalls during viewport and compositor work.
                # This is a soft preference: we don't hard-block but
                # the scoring system rewards these via cpu_score_int.
                # [CPU: L3 Cache] [CPU: Series]
                # (Scoring handled in performance_scores.py — no hard constraint here)

    # ── SMT CHECK (content creator global) ───────────────────────────────────
    # CPUs without SMT waste half the silicon in multi-threaded render workloads.
    # Hard-block non-SMT CPUs only for content creation.
    # [CPU: Simultaneous Multithreading]
    if is_cc:
        for c in range(len(cpu_df)):
            cpu_row = cpu_df.loc[c]
            if not _has_smt(cpu_row):
                model.Add(cpu_vars[c] == 0)

    return model
