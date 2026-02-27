# PC Build Recommendation System 💻
### Multi-use-case | 7 components | Circuit-based motherboard filtering

---

## What's Different From xo-receng

| Feature | xo-receng (original) | This project |
|---|---|---|
| Components | CPU, GPU, Mobo, RAM | + Storage, PSU, Cooler |
| Use cases | Gaming only | Gaming, Productivity, Content Creation |
| Mobo filter | Socket + chipset name | + VRM phases, PCIe version, M.2 slots, USB count, WiFi |
| CPU scoring | Cache, boost, litho, SMT, X3D, price efficiency | Same + use-case variants |
| GPU scoring | VRAM × boost_clock | Same + VRAM-weighted variants for productivity/content |

---

## Project Structure

```
.
├── main.py                          # Entry point
├── solver.py                        # CP-SAT solver + result display
├── config.py                        # All constants and thresholds
├── data_loader.py                   # CSV loading
├── data_cleaner.py                  # Data cleaning (extended from original)
├── requirements.txt
│
├── constraints/
│   ├── base_constraints.py          # Exactly-one + budget range
│   ├── cpu_constraints.py           # Floor, gen rules, bottleneck prevention
│   ├── gpu_constraints.py           # VRAM floor, tier pairing, gen dominance
│   ├── mobo_constraints.py          # ★ Circuit-based (VRM/PCIe/M.2/USB/WiFi) + compat
│   ├── ram_constraints.py           # DDR compat, capacity scaling
│   ├── storage_constraints.py       # NVMe preference, capacity by budget
│   ├── psu_constraints.py           # Efficiency + wattage range
│   └── cooler_constraints.py        # TDP coverage, AIO vs air, room conditions
│
├── scoring/
│   └── performance_scores.py        # CPU + GPU scoring (original formula + use-case variants)
│
├── utils/
│   └── helpers.py                   # All parsing, identification, circuit, PSU helpers
│
└── data_files/                      # Put your CSVs here
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
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

---

## CSV Formats

### cpu_data.csv
Uses same column names as xo-receng:
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
Original columns + new circuit columns:
```
Name, Price, Socket/CPU, Memory Slots, Memory Max,
VRM_Phases, PCIe_Version, M2_Slots, USB_Count, WiFi
```

**VRM_Phases**: integer (e.g. 8)
**PCIe_Version**: integer (e.g. 4 or 5)
**M2_Slots**: integer (e.g. 2)
**USB_Count**: integer (e.g. 8)
**WiFi**: yes / no

### ram_data.csv
```
Name, Price, Speed, Modules
```
Modules format: `2 x 16GB`

### storage_data.csv
```
Name, Price
```
Capacity parsed from name (e.g. `Samsung 990 Pro 1TB NVMe M.2`)

### psu_data.csv
```
Name, Price, Wattage, Efficiency
```
Efficiency: Bronze / Gold / Platinum / Titanium

### cooler_data.csv
```
Name, Price, TDP_Rating, Type
```
Type: air / aio / liquid

---

## Circuit-Based Motherboard Filtering

The key addition in this project. Filters boards on actual circuit specs not just socket/chipset names.

### VRM Phases (power delivery quality)
| Budget Tier | Min Phases |
|---|---|
| Entry (<1L) | 4 |
| Low (1-2L) | 6 |
| Mid (2-4L) | 8 |
| High (4-7L) | 10 |
| Ultra (7L+) | 12 |

### PCIe Version (GPU bandwidth)
| Budget Tier | Min Version |
|---|---|
| Entry/Low | 3/4 |
| Mid | 4 |
| High/Ultra | 5 |

Flagship GPUs (RTX 5080/5090, RX 7900 XTX) are paired only with PCIe 5.0 boards.

### M.2 Slots
| Budget Tier | Min Slots |
|---|---|
| Entry | 1 |
| Low/Mid | 2 |
| High/Ultra | 3 |

### USB Count
| Budget Tier | Min Ports |
|---|---|
| Entry | 4 |
| Low/Mid | 6 |
| High | 8 |
| Ultra | 10 |

---

## Performance Scoring

Original `cpu_gaming_score` formula preserved exactly:
```
score = log1p(l3_cache)×32 + boost×22 + core_score + arch_bonus + smt_bonus + x3d_bonus
```
With price efficiency scaling that weakens at higher budgets (original logic).

GPU gaming score preserved: `vram × boost_clock`

Use-case variants adjust weights — productivity favours cores and SMT, content creation balances both.

---

## Customisation

All thresholds in `config.py`:
- `VRM_TIERS` — VRM phase minimums per tier
- `PCIE_MIN_VERSION` — PCIe version minimums
- `M2_MIN_SLOTS` — M.2 slot minimums
- `USB_MIN_COUNT` — USB port minimums
- `USE_CASE_WEIGHTS` — CPU/GPU score weights per use case
