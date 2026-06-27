from pathlib import Path

# amg_pv_bess_advisor/core/hydro_project/config.py

# HYDRO_DIR = amg_pv_bess_advisor/core/hydro_project
HYDRO_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT = amg_pv_bess_advisor
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# amg_pv_bess_advisor/data/hydroelectric_data
DATA_DIR = PROJECT_ROOT / "data" / "hydroelectric_data"

# amg_pv_bess_advisor/outputs/hydro_project
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "hydro_project"

INPUT_FILES = [
    DATA_DIR / "Muc nuoc ho Ham Thuan 5-2025.xlsx",
    DATA_DIR / "Muc nuoc ho Ham Thuan 6-2025.xlsx",
    DATA_DIR / "Muc nuoc ho Ham Thuan 7-2025.xlsx",
]

RHO_WATER = 1000.0     # kg/m3
GRAVITY = 9.81         # m/s2

DEFAULT_EFFICIENCY = 0.90
DEFAULT_TAILWATER_LEVEL = 0.0
DEFAULT_HYDRAULIC_LOSS = 0.0