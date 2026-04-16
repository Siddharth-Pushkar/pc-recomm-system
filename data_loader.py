"""
Data loading — reads core 4 CSVs only (CPU, GPU, MOBO, RAM)
PSU, Cooler, Storage are no longer loaded as datasets.
"""
import os
import pandas as pd
from data_cleaner import (
    clean_cpu_data, clean_gpu_data, clean_mobo_data, clean_ram_data
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_files")

CSV_FILES = {
    "cpu":  "cpu_data.csv",
    "gpu":  "gpu_data.csv",
    "mobo": "motherboard_data.csv",
    "ram":  "ram_data.csv",
}

CLEANERS = {
    "cpu":  clean_cpu_data,
    "gpu":  clean_gpu_data,
    "mobo": clean_mobo_data,
    "ram":  clean_ram_data,
}


def load_and_clean_data():
    """
    Load and clean core 4 component DataFrames.
    Returns: cpu_df, gpu_df, mobo_df, ram_df
    """
    dfs = {}
    for key, filename in CSV_FILES.items():
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"\n[DataLoader] Missing file: {path}\n"
                f"Please add '{filename}' to the data_files/ folder."
            )
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        df = CLEANERS[key](df)
        print(f"  ✔  {key.upper():<8} — {len(df)} components loaded")
        dfs[key] = df

    return dfs["cpu"], dfs["gpu"], dfs["mobo"], dfs["ram"]
