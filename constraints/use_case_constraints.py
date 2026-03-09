"""
Use-Case Optimisation Constraints  —  Content Creator Sub-Categories
=====================================================================
Covers sub-categories:
  - video_editing   : VRAM floors, NVIDIA preference for DaVinci, NVMe
  - rendering_3d    : Core count floors, VRAM for GPU render, PSU sustained load
  - motion_graphics : RAM 64 GB, fast RAM speed, GPU VRAM
  - ai_ml           : VRAM ≥ 16 GB, NVIDIA CUDA, GDDR7, PCIe 5.0
  - photo_editing   : Single-core boost clock, NVMe, RAM 32 GB
  - music_production: Single-core boost clock, USB count, RAM, GPU irrelevance

Sub-category is passed as a string via the `sub_category` parameter.
If sub_category is None or empty, only the base content_creation rules apply.

Doc ref: "USE-CASE OPTIMISATION (Content Creator Sub-Categories)"
"""
import re
from utils.helpers import get_int, get_ghz, get_watts, get_budget_tier


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_vram_gb(gpu_row) -> int:
    """[GPU: Memory]"""
    val = str(gpu_row.get("Memory", gpu_row.get("memory", "0")))
    m = re.search(r"(\d+)", val)
    return int(m.group(1)) if m else 0


def _get_memory_type(gpu_row) -> str:
    """[GPU: Memory Type]"""
    return str(gpu_row.get("Memory Type",
                           gpu_row.get("memory_type", ""))).strip().upper()


def _is_nvidia_gpu(gpu_row) -> bool:
    """[GPU: Chipset]"""
    chipset = str(gpu_row.get("Chipset", gpu_row.get("chipset", ""))).lower()
    name    = str(gpu_row.get("Name",    gpu_row.get("name",    ""))).lower()
    return "rtx" in chipset or "gtx" in chipset or "geforce" in chipset \
        or "rtx" in name  or "gtx" in name  or "geforce" in name


def _get_core_count(cpu_row) -> int:
    """[CPU: Core Count]"""
    return get_int(cpu_row.get("Core Count", cpu_row.get("core_count", 0)), 0)


def _get_boost_clock_ghz(cpu_row) -> float:
    """[CPU: Performance Core Boost Clock]"""
    for col in ("Performance Core Boost Clock", "boost_clock",
                "Boost Clock", "Core Boost Clock"):
        if col in cpu_row.index:
            v = get_ghz(cpu_row[col], 0.0)
            if v > 0:
                return v
    return 0.0


def _parse_modules(modules_str: str):
    """Returns (sticks, per_stick_gb, total_gb)"""
    s = str(modules_str).replace(" ", "").upper()
    m = re.match(r"(\d+)X(\d+)GB", s)
    if m:
        sticks    = int(m.group(1))
        per_stick = int(m.group(2))
        return sticks, per_stick, sticks * per_stick
    m2 = re.search(r"(\d+)GB", s)
    if m2:
        total = int(m2.group(1))
        return 1, total, total
    return 0, 0, 0


def _get_usb_count(mobo_row) -> int:
    """[MOBO: USB_Count]"""
    from utils.helpers import get_usb_count
    return get_usb_count(mobo_row)


def _get_pcie_version(mobo_row) -> int:
    """[MOBO: PCIe_Version]"""
    from utils.helpers import get_pcie_version
    return get_pcie_version(mobo_row)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONSTRAINT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def add_use_case_constraints(model,
                             cpu_df,     cpu_vars,
                             gpu_df,     gpu_vars,
                             ram_df,     ram_vars,
                             mobo_df,    mobo_vars,
                             budget:     int,
                             use_case:   str = "content_creation",
                             sub_category: str = None):
    """
    Apply content creator sub-category constraints.

    Parameters
    ----------
    model        : CP-SAT CpModel
    cpu_df/vars  : CPU dataframe and BoolVars
    gpu_df/vars  : GPU dataframe and BoolVars
    ram_df/vars  : RAM dataframe and BoolVars
    mobo_df/vars : Motherboard dataframe and BoolVars
    budget       : total build budget in INR
    use_case     : must be "content_creation" for these constraints to activate
    sub_category : "video_editing" | "rendering_3d" | "motion_graphics" |
                   "ai_ml" | "photo_editing" | "music_production" | None
    """

    if use_case != "content_creation":
        return model  # nothing to do for other use cases here

    tier = get_budget_tier(budget)
    sub  = (sub_category or "").lower().strip()

    # ══════════════════════════════════════════════════════════════
    # VIDEO EDITING  (Premiere, DaVinci Resolve, Final Cut)
    # ══════════════════════════════════════════════════════════════
    if sub == "video_editing":

        for g in range(len(gpu_df)):
            gpu_row = gpu_df.loc[g]
            vram    = _get_vram_gb(gpu_row)

            # VRAM floor: 12 GB for 4K, 16 GB for 8K
            # Frame buffers for full-res playback live entirely in VRAM.
            # [GPU: Memory]
            if tier in ("mid", "high", "ultra"):
                if vram > 0 and vram < 12:
                    model.Add(gpu_vars[g] == 0)
            if tier in ("high", "ultra"):
                if vram > 0 and vram < 16:
                    model.Add(gpu_vars[g] == 0)

            # NVIDIA preference for DaVinci Resolve
            # CUDA acceleration is significantly faster than OpenCL.
            # Hard constraint at mid+ tier where NVIDIA alternatives exist.
            # [GPU: Chipset]
            if tier in ("mid", "high", "ultra"):
                if not _is_nvidia_gpu(gpu_row):
                    model.Add(gpu_vars[g] == 0)

        # RAM ≥ 32 GB (64 GB for heavy 6K/8K or multi-cam)
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 32:
                model.Add(ram_vars[r] == 0)
            if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
                model.Add(ram_vars[r] == 0)

        # NVMe storage: enforce at least 2 M.2 slots on motherboard
        # SATA SSD is insufficient for 4K RAW sustained reads (< 3500 MB/s).
        # [MOBO: M.2 Slots]
        for m in range(len(mobo_df)):
            mobo_row = mobo_df.loc[m]
            from utils.helpers import get_m2_slots
            m2 = get_m2_slots(mobo_row)
            if m2 > 0 and m2 < 2:
                model.Add(mobo_vars[m] == 0)

    # ══════════════════════════════════════════════════════════════
    # 3D RENDERING  (Blender, Cinema 4D, Houdini)
    # ══════════════════════════════════════════════════════════════
    elif sub == "rendering_3d":

        # CPU core count ≥ 12 — render time scales linearly with cores.
        # This is the single most impactful spec for CPU rendering.
        # [CPU: Core Count]
        for c in range(len(cpu_df)):
            cpu_row = cpu_df.loc[c]
            cores   = _get_core_count(cpu_row)
            if cores > 0 and cores < 12:
                model.Add(cpu_vars[c] == 0)

        for g in range(len(gpu_df)):
            gpu_row = gpu_df.loc[g]
            vram    = _get_vram_gb(gpu_row)

            # GPU VRAM ≥ 16 GB for GPU rendering
            # Scenes exceeding VRAM fall back to system RAM: 10–50× slower.
            # [GPU: Memory]
            if tier in ("mid", "high", "ultra"):
                if vram > 0 and vram < 16:
                    model.Add(gpu_vars[g] == 0)

        # RAM ≥ 32 GB minimum; 64 GB for complex scenes
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 32:
                model.Add(ram_vars[r] == 0)
            if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
                model.Add(ram_vars[r] == 0)

        # NOTE: X3D CPUs give diminishing returns for render (compute-bound,
        # not cache-bound). The scoring system reduces X3D bonus for this
        # sub-category. No hard constraint needed here.
        # [CPU: Core Count] [CPU: L3 Cache]

    # ══════════════════════════════════════════════════════════════
    # MOTION GRAPHICS & VFX  (After Effects, DaVinci Fusion)
    # ══════════════════════════════════════════════════════════════
    elif sub == "motion_graphics":

        # RAM ≥ 64 GB
        # After Effects caches entire composition frames in RAM.
        # More RAM = longer cached preview without re-render.
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 64:
                model.Add(ram_vars[r] == 0)

        # GPU VRAM ≥ 12 GB for GPU-accelerated effects
        # [GPU: Memory]
        for g in range(len(gpu_df)):
            gpu_row = gpu_df.loc[g]
            vram    = _get_vram_gb(gpu_row)
            if tier in ("mid", "high", "ultra") and vram > 0 and vram < 12:
                model.Add(gpu_vars[g] == 0)

    # ══════════════════════════════════════════════════════════════
    # AI / ML  (Stable Diffusion, LoRA training, inference)
    # ══════════════════════════════════════════════════════════════
    elif sub == "ai_ml":

        for g in range(len(gpu_df)):
            gpu_row     = gpu_df.loc[g]
            vram        = _get_vram_gb(gpu_row)
            mem_type    = _get_memory_type(gpu_row)
            is_nvidia   = _is_nvidia_gpu(gpu_row)

            # VRAM ≥ 16 GB — model weights live in VRAM.
            # Smaller VRAM forces quantisation, degrading output quality.
            # [GPU: Memory]
            if vram > 0 and vram < 16:
                model.Add(gpu_vars[g] == 0)

            # Strongly prefer NVIDIA — CUDA ecosystem for ML is far more
            # mature than AMD ROCm for most frameworks (PyTorch, TensorFlow).
            # Hard constraint at mid+ tier.
            # [GPU: Chipset] [GPU: Memory Type]
            if tier in ("mid", "high", "ultra") and not is_nvidia:
                model.Add(gpu_vars[g] == 0)

            # GDDR7 preferred — higher bandwidth reduces data starvation
            # during matrix multiply operations.
            # Soft: only hard-enforce at ultra tier.
            # [GPU: Memory Type]
            if tier == "ultra" and mem_type and "GDDR7" not in mem_type:
                model.Add(gpu_vars[g] == 0)

        # PCIe 5.0 x16 preferred for model weight transfer bandwidth
        # Hard-enforce at high/ultra tier.
        # [MOBO: PCIe_Version]
        if tier in ("high", "ultra"):
            for m in range(len(mobo_df)):
                mobo_row = mobo_df.loc[m]
                pcie = _get_pcie_version(mobo_row)
                if pcie > 0 and pcie < 5:
                    model.Add(mobo_vars[m] == 0)

        # RAM ≥ 32 GB (64 GB preferred for large model fine-tuning)
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 32:
                model.Add(ram_vars[r] == 0)
            if tier in ("high", "ultra") and total_gb > 0 and total_gb < 64:
                model.Add(ram_vars[r] == 0)

    # ══════════════════════════════════════════════════════════════
    # PHOTO EDITING & BATCH PROCESSING  (Lightroom, Photoshop)
    # ══════════════════════════════════════════════════════════════
    elif sub == "photo_editing":

        # High single-core boost clock priority
        # Photoshop and Lightroom are not heavily multi-threaded.
        # Enforce minimum boost clock at mid+ tier.
        # [CPU: Performance Core Boost Clock]
        MIN_BOOST_GHZ = 4.5
        for c in range(len(cpu_df)):
            cpu_row    = cpu_df.loc[c]
            boost      = _get_boost_clock_ghz(cpu_row)
            if tier in ("mid", "high", "ultra") and boost > 0 and boost < MIN_BOOST_GHZ:
                model.Add(cpu_vars[c] == 0)

        # RAM ≥ 32 GB
        # Lightroom catalogue and cache are RAM-hungry.
        # Batch exports of 100+ RAW files saturate RAM.
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 32:
                model.Add(ram_vars[r] == 0)

        # NVMe minimum: at least 2 M.2 slots
        # Fast NVMe is more impactful than GPU tier for Lightroom.
        # Catalogue reads and preview generation are storage-bound.
        # [MOBO: M.2 Slots]
        for m in range(len(mobo_df)):
            mobo_row = mobo_df.loc[m]
            from utils.helpers import get_m2_slots
            m2 = get_m2_slots(mobo_row)
            if m2 > 0 and m2 < 2:
                model.Add(mobo_vars[m] == 0)

    # ══════════════════════════════════════════════════════════════
    # MUSIC PRODUCTION / DAW  (FL Studio, Ableton, Logic)
    # ══════════════════════════════════════════════════════════════
    elif sub == "music_production":

        # High single-core boost clock priority
        # DAWs are single-threaded per plugin instance.
        # [CPU: Performance Core Boost Clock]
        MIN_BOOST_GHZ = 4.8
        for c in range(len(cpu_df)):
            cpu_row = cpu_df.loc[c]
            boost   = _get_boost_clock_ghz(cpu_row)
            if tier in ("mid", "high", "ultra") and boost > 0 and boost < MIN_BOOST_GHZ:
                model.Add(cpu_vars[c] == 0)

        # RAM ≥ 32 GB if using large sample libraries
        # Sample streaming from RAM is the dominant memory pattern.
        # [RAM: Modules]
        for r in range(len(ram_df)):
            ram_row = ram_df.loc[r]
            _, _, total_gb = _parse_modules(
                ram_row.get("Modules", ram_row.get("modules", ""))
            )
            if total_gb > 0 and total_gb < 32:
                model.Add(ram_vars[r] == 0)

        # USB count ≥ 6 — audio interfaces require dedicated USB bandwidth.
        # Low-latency ASIO drivers compete for USB controller bandwidth.
        # [MOBO: USB_Count]
        for m in range(len(mobo_df)):
            mobo_row = mobo_df.loc[m]
            usb = _get_usb_count(mobo_row)
            if usb > 0 and usb < 6:
                model.Add(mobo_vars[m] == 0)

        # GPU is nearly irrelevant for pure audio production.
        # Allow any GPU that fits the budget — no GPU constraint here.
        # Budget can be reallocated to CPU and RAM via solver scoring weights.

    return model
