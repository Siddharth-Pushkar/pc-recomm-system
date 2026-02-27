# PC Build Recommendation System 💻
### Multi-use-case · 7 components · Circuit-based motherboard filtering

Built as part of the **XO Rig** internship project. An improved constraint-programming recommendation engine on top of the original `xo-receng`, with expanded component coverage, multi-use-case scoring, and circuit-level motherboard filtering.

---

## What's New vs. xo-receng

| Feature | xo-receng (original) | This version |
|---|---|---|
| Components | CPU, GPU, Mobo, RAM | + Storage, PSU, Cooler (7 total) |
| Use cases | Gaming only | Gaming, Productivity, Content Creation |
| Motherboard filtering | Socket + chipset name | + VRM phases, PCIe version, M.2 slots, USB count, WiFi |
| CPU scoring | Cache, boost, litho, SMT, X3D, price efficiency | Same + use-case weighted variants |
| GPU scoring | VRAM × boost clock | Same + VRAM-weighted variants for productivity/content |

---

## Project Structure

```
.
├── main.py                       # Entry point
├── solver.py                     # CP-SAT solver + result display
├── config.py                     # All constants and thresholds
├── data_loader.py                # CSV loading
├── data_cleaner.py               # Data cleaning (extended from original)
├── requirements.txt
│
├── constraints/
│   ├── base_constraints.py       # Exactly-one + budget range
│   ├── cpu_constraints.py        # Floor, generation rules, bottleneck prevention
│   ├── gpu_constraints.py        # VRAM floor, tier pairing, gen dominance
│   ├── mobo_constraints.py       # ★ Circuit-based filtering + socket/DDR compat
│   ├── ram_constraints.py        # DDR compat, capacity scaling
│   ├── storage_constraints.py    # NVMe preference, capacity by budget
│   ├── psu_constraints.py        # Efficiency tier + wattage range
│   └── cooler_constraints.py     # TDP coverage, AIO vs air, room conditions
│
├── scoring/
│   └── performance_scores.py     # CPU + GPU scoring (original + use-case variants)
│
├── utils/
│   └── helpers.py                # Parsing, identification, circuit + PSU helpers
│
└── data_files/
    ├── cpu_data.csv
    ├── gpu_data.csv
    ├── motherboard_data.csv
    ├── ram_data.csv
    ├── storage_data.csv
    ├── psu_data.csv
    └── cooler_data.csv
```

---

## Getting Started

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

You'll be prompted for:
1. **Total budget** (in INR)
2. **Use case** — Gaming, Productivity, or Content Creation
3. **Room conditions** — dusty/warm (affects cooler recommendation)

---

## CSV Formats

### cpu_data.csv
Column names match xo-receng exactly:
```
Name, Price (INR Formatted), Core Count, TDP,
Performance Core Clock, Performance Core Boost Clock,
L3 Cache, Lithography, Simultaneous Multithreading, Socket
```

### gpu_data.csv
```
Name, Price, Memory, TDP, Boost Clock, Manufacturer
```

### motherboard_data.csv
Original columns + 5 new circuit columns:
```
Name, Price, Socket/CPU, Memory Slots, Memory Max,
VRM_Phases, PCIe_Version, M2_Slots, USB_Count, WiFi
```

| Column | Format | Example |
|---|---|---|
| `VRM_Phases` | integer | `12` |
| `PCIe_Version` | integer | `4` or `5` |
| `M2_Slots` | integer | `2` |
| `USB_Count` | integer | `8` |
| `WiFi` | `yes` / `no` | `yes` |

### ram_data.csv
```
Name, Price, Speed, Modules
```
`Modules` format: `2 x 16GB`

### storage_data.csv
```
Name, Price
```
Capacity is parsed from the name — e.g. `Samsung 990 Pro 1TB NVMe M.2`

### psu_data.csv
```
Name, Price, Wattage, Efficiency
```
`Efficiency` values: `Bronze` / `Gold` / `Platinum` / `Titanium`

### cooler_data.csv
```
Name, Price, TDP_Rating, Type
```
`Type` values: `air` / `aio` / `liquid`

---

## Circuit-Based Motherboard Filtering

The key addition in this project. Instead of filtering motherboards by socket/chipset name alone, boards are evaluated on actual circuit-level specs. All thresholds are configurable in `config.py`.

### VRM Phases — Power delivery quality

| Budget Tier | Budget Range | Min Phases |
|---|---|---|
| Entry | < ₹1,00,000 | 4 |
| Low | ₹1L – ₹2L | 6 |
| Mid | ₹2L – ₹4L | 8 |
| High | ₹4L – ₹7L | 10 |
| Ultra | ₹7L+ | 12 |

### PCIe Version — GPU bandwidth

| Budget Tier | Min Version |
|---|---|
| Entry / Low | 3 or 4 |
| Mid | 4 |
| High / Ultra | 5 |

Flagship GPUs (RTX 5080, RTX 5090, RX 7900 XTX) are paired only with PCIe 5.0 boards.

### M.2 Slots — Storage expandability

| Budget Tier | Min Slots |
|---|---|
| Entry | 1 |
| Low / Mid | 2 |
| High / Ultra | 3 |

### USB Count — Connectivity

| Budget Tier | Min Ports |
|---|---|
| Entry | 4 |
| Low / Mid | 6 |
| High | 8 |
| Ultra | 10 |

### WiFi
High and Ultra tier builds require onboard WiFi. Lower tiers allow wired-only boards.

---

## Performance Scoring

The original `cpu_gaming_score` formula is preserved exactly:

```
score = log1p(l3_cache)×32 + boost×22 + core_score + arch_bonus + smt_bonus + x3d_bonus
```

Price efficiency scaling weakens at higher budgets (original behaviour kept).

GPU gaming score formula also preserved: `vram × boost_clock`

Use-case variants adjust the weights applied during solver optimisation:

| Use Case | CPU Weight | GPU Weight | Notes |
|---|---|---|---|
| Gaming | 0.8 | 2.6 | GPU-heavy, original weights |
| Productivity | 1.4 | 1.2 | Cores + SMT prioritised |
| Content Creation | 1.1 | 1.8 | Balanced, VRAM-weighted GPU score |

---

## Customisation

All thresholds live in `config.py`:

```python
VRM_TIERS         # VRM phase minimums per budget tier
PCIE_MIN_VERSION  # PCIe version minimums per tier
M2_MIN_SLOTS      # M.2 slot minimums per tier
USB_MIN_COUNT     # USB port minimums per tier
USE_CASE_WEIGHTS  # CPU/GPU score weights per use case

BUDGET_THRESHOLDS = {
    'entry': 100000,
    'low':   200000,
    'mid':   450000,
    'high':  700000,
}
```

---

## Key Technologies

- **Google OR-Tools (CP-SAT)** — constraint programming solver
- **Pandas** — data loading and cleaning
- **NumPy** — numerical operations
- **Python 3.8+**

---

## Data Notes

Component data was scraped from Indian retail websites and PCPartPicker. Prices reflect market rates as of early 2025. Update the CSVs in `data_files/` for current pricing.

The `motherboard_data.csv` circuit columns (`VRM_Phases`, `PCIe_Version`, `M2_Slots`, `USB_Count`, `WiFi`) were derived from raw PCPartPicker spec data. `VRM_Phases` in particular is estimated from chipset tier where manufacturer data was unavailable.