"""
PC Build Recommendation System — Entry Point
Routes to the correct engine based on use case.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from engines.gaming_engine       import run_gaming_engine
from engines.productivity_engine import run_productivity_engine
from engines.content_engine      import run_content_engine


USE_CASES = {"1": "gaming", "2": "productivity", "3": "content_creation"}

SUB_CATEGORIES = {
    "1": "video_editing",
    "2": "rendering_3d",
    "3": "motion_graphics",
    "4": "ai_ml",
    "5": "photo_editing",
    "6": "music_production",
}


def get_inputs():
    print("\n" + "═" * 58)
    print("        🖥️   PC BUILD RECOMMENDATION SYSTEM")
    print("═" * 58)

    # ── Budget ────────────────────────────────────────────────────
    while True:
        try:
            budget = int(input("\nEnter total PC budget (₹ INR): ").replace(",", "").strip())
            if budget < 30000:
                print("  ⚠  Minimum budget is ₹30,000.")
                continue
            break
        except ValueError:
            print("  ⚠  Please enter a valid number.")

    # ── Use case ──────────────────────────────────────────────────
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

    # ── Sub-category (content creation only) ─────────────────────
    sub_category = None
    if use_case == "content_creation":
        print("\nSelect content creation type:")
        print("  1. Video Editing         (Premiere, DaVinci Resolve)")
        print("  2. 3D Rendering          (Blender, Cinema 4D, Houdini)")
        print("  3. Motion Graphics / VFX (After Effects, DaVinci Fusion)")
        print("  4. AI / ML               (Stable Diffusion, LoRA training)")
        print("  5. Photo Editing         (Lightroom, Photoshop)")
        print("  6. Music Production      (FL Studio, Ableton, Logic)")
        while True:
            sc = input("Enter choice (1–6): ").strip()
            if sc in SUB_CATEGORIES:
                sub_category = SUB_CATEGORIES[sc]
                break
            print("  ⚠  Enter 1 to 6.")

    # ── WiFi ──────────────────────────────────────────────────────
    wifi = input("\nDo you need onboard WiFi? (yes/no): ").strip().lower()
    require_wifi = wifi in ("yes", "y")

    return budget, use_case, sub_category, require_wifi


def main():
    budget, use_case, sub_category, require_wifi = get_inputs()

    if use_case == "gaming":
        run_gaming_engine(budget, require_wifi)

    elif use_case == "productivity":
        run_productivity_engine(budget, require_wifi)

    elif use_case == "content_creation":
        run_content_engine(budget, sub_category, require_wifi)


if __name__ == "__main__":
    main()
