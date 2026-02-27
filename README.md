# PC Build Recommendation System 💻
### Multi-use-case · 7 components · Circuit-based motherboard filtering

An intelligent PC build recommendation system that uses **constraint programming** with Google OR-Tools to find the optimal component configuration for your budget and use case. Built for the Indian market — budgets in INR, components sourced from Indian retailers.

---

## Features

- **Constraint-Based Optimisation** — CP-SAT solver picks the best compatible set of components, not just the cheapest or most expensive
- **7 Component Categories** — CPU, GPU, Motherboard, RAM, Storage, PSU, Cooler
- **3 Use Cases** — Gaming, Productivity, Content Creation (each with tuned scoring weights)
- **Circuit-Based Motherboard Filtering** — filters boards on VRM phases, PCIe version, M.2 slots, USB count, and WiFi — not just socket/chipset name
- **Budget-Aware Allocation** — automatically calculates per-component budget ranges based on tier and use case
- **Compatibility Checking** — socket, DDR type, TDP, and PSU wattage all enforced
- **Smart Cooling Recommendations** — accounts for CPU TDP, budget tier, and room conditions (dusty/warm)

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/pc-build-recommender.git
cd pc-build-recommender

# 2. Create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
python main.py
```

You'll be prompted for:
1. **Total budget** (INR)
2. **Use case** — Gaming, Productivity, or Content Creation
3. **Room conditions** — dusty/warm (affects cooler recommendation)

### Example Output

```
Enter total PC budget (INR): 150000
Use case (gaming/productivity/content): gaming
Is your room dusty and warm? (yes/no): no

Core component budget range: ₹1,20,000 – ₹1,35,000
Data loaded & cleaned ✓

BEST BUILD FOUND

CPU         : AMD Ryzen 5 7600X               ₹25,000
GPU         : NVIDIA GeForce RTX 4060 Ti      ₹45,000
Motherboard : MSI B650M PRO-A                 ₹15,000
RAM         : G.Skill Ripjaws 32GB DDR5-6000  ₹12,000
Storage     : Samsung 990 Pro 1TB NVMe        ₹10,000
PSU         : Corsair CV650 80+ Bronze        ₹7,000
Cooler      : DeepCool AK400                  ₹3,500

Cooling Recommendation : 240mm AIO Liquid Cooler
Recommended PSU        : 80+ Gold 750W (CPU 105W + GPU 160W)

Total Core Component Cost: ₹1,17,500
```

---

## Project Structure

```
.
├── main.py                       # Entry point
├── solver.py                     # CP-SAT solver + result display
├── config.py                     # All constants and thresholds
├── data_loader.py                # CSV loading
├── data_cleaner.py               # Data cleaning
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
│   └── performance_scores.py     # CPU + GPU scoring with use-case variants
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

## How It Works

### 1. Data Loading & Cleaning
Loads all CSVs from `data_files/`, standardises names, prices, and specs, and drops rows with missing critical values.

### 2. Budget Allocation
Before solving, the system calculates per-component budget bands based on total budget and use case tier. GPU gets more headroom in gaming builds; CPU and RAM get more in productivity builds.

### 3. Constraint Programming Model
Boolean variables are created for each component. The CP-SAT solver must satisfy:

- Exactly one component selected per category
- Total cost within the calculated budget range
- CPU ↔ Motherboard socket compatibility
- RAM DDR type matches motherboard
- PSU wattage covers CPU TDP + GPU TDP with headroom
- Motherboard meets circuit-level minimums for the budget tier (see below)

### 4. Optimisation Objective
Maximises a weighted performance score:

```
Performance = (CPU_score × cpu_weight) + (GPU_score × gpu_weight)
```

Weights vary by use case:

| Use Case | CPU Weight | GPU Weight |
|---|---|---|
| Gaming | 0.8 | 2.6 |
| Productivity | 1.4 | 1.2 |
| Content Creation | 1.1 | 1.8 |

### 5. Output
Selected components with prices, cooling recommendation, PSU spec, and total cost.

---

## Circuit-Based Motherboard Filtering

Standard recommendation systems filter motherboards by socket and chipset name. This system goes further — filtering on actual circuit-level specs so board quality scales with the budget.

### VRM Phases — Power delivery quality

| Tier | Budget | Min Phases |
|---|---|---|
| Entry | < ₹1,00,000 | 4 |
| Low | ₹1L – ₹2L | 6 |
| Mid | ₹2L – ₹4L | 8 |
| High | ₹4L – ₹7L | 10 |
| Ultra | ₹7L+ | 12 |

### PCIe Version — GPU bandwidth

| Tier | Min Version |
|---|---|
| Entry / Low | 4 |
| Mid | 4 |
| High / Ultra | 5 |

Flagship GPUs (RTX 5080, RTX 5090, RX 7900 XTX) are paired only with PCIe 5.0 boards.

### M.2 Slots — Storage expandability

| Tier | Min Slots |
|---|---|
| Entry | 1 |
| Low / Mid | 2 |
| High / Ultra | 3 |

### USB Count — Connectivity

| Tier | Min Ports |
|---|---|
| Entry | 4 |
| Low / Mid | 6 |
| High | 8 |
| Ultra | 10 |

### WiFi
High and Ultra tier builds require onboard WiFi. Lower tiers allow wired-only boards.

---

## Performance Scoring

### CPU Score
```
score = log1p(l3_cache)×32 + boost×22 + core_score + arch_bonus + smt_bonus + x3d_bonus
```
Price efficiency scaling is applied but weakens at higher budgets to avoid penalising premium parts.

### GPU Score
```
score = vram × boost_clock
```
Content Creation and Productivity variants apply additional VRAM weighting.

---

## CSV Format Reference

### cpu_data.csv
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
```
Name, Price, Socket/CPU, Memory Slots, Memory Max,
VRM_Phases, PCIe_Version, M2_Slots, USB_Count, WiFi
```

| Column | Type | Example |
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
Capacity parsed from name — e.g. `Samsung 990 Pro 1TB NVMe M.2`

### psu_data.csv
```
Name, Price, Wattage, Efficiency
```
`Efficiency`: `Bronze` / `Gold` / `Platinum` / `Titanium`

### cooler_data.csv
```
Name, Price, TDP_Rating, Type
```
`Type`: `air` / `aio` / `liquid`

---

## Customisation

All thresholds live in `config.py`:

```python
BUDGET_THRESHOLDS = {
    'entry': 100000,
    'low':   200000,
    'mid':   450000,
    'high':  700000,
}

VRM_TIERS        # Min VRM phases per budget tier
PCIE_MIN_VERSION # Min PCIe version per tier
M2_MIN_SLOTS     # Min M.2 slots per tier
USB_MIN_COUNT    # Min USB ports per tier
USE_CASE_WEIGHTS # CPU/GPU score weights per use case
```

To add a new constraint, create a module in `constraints/` following the pattern of any existing file and register it in `solver.py`.

---

## Tech Stack

- **[Google OR-Tools](https://developers.google.com/optimization)** — CP-SAT constraint solver
- **[Pandas](https://pandas.pydata.org/)** — data loading and cleaning
- **[NumPy](https://numpy.org/)** — numerical operations
- **Python 3.8+**

---

## Data Notes

Component data was scraped from Indian retail websites and PCPartPicker. Prices reflect market rates as of early 2025 — update the CSVs in `data_files/` for current pricing.

The motherboard circuit columns (`VRM_Phases`, `PCIe_Version`, `M2_Slots`, `USB_Count`, `WiFi`) were derived from raw PCPartPicker spec data. `VRM_Phases` is estimated from chipset tier where direct manufacturer data was unavailable.

---
