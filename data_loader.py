"""
Data loading — reads CSVs and runs them through data_cleaner.py
"""
import os
import pandas as pd
from data_cleaner import (
    clean_cpu_data, clean_gpu_data, clean_mobo_data,
    clean_ram_data, clean_storage_data, clean_psu_data, clean_cooler_data
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_files")

CSV_FILES = {
    "cpu":     "cpu_data_280.csv",
    "gpu":     "gpu_data_280.csv",
    "mobo":    "motherboard_data_280.csv",
    "ram":     "ram_data_280.csv",
    "storage": "storage_data.csv",
    "psu":     "psu_data.csv",
    "cooler":  "cooler_data.csv",
}

CLEANERS = {
    "cpu":     clean_cpu_data,
    "gpu":     clean_gpu_data,
    "mobo":    clean_mobo_data,
    "ram":     clean_ram_data,
    "storage": clean_storage_data,
    "psu":     clean_psu_data,
    "cooler":  clean_cooler_data,
}


def load_and_clean_data():
    """
    Load and clean all component DataFrames.
    Returns: cpu_df, gpu_df, mobo_df, ram_df, storage_df, psu_df, cooler_df
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

    return (
        dfs["cpu"], dfs["gpu"], dfs["mobo"], dfs["ram"],
        dfs["storage"], dfs["psu"], dfs["cooler"]
    )
