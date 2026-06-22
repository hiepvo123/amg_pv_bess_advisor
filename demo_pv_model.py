"""
demo_pv_model.py

Runs the PV module (core/pv_model.py) on the project's real data,
producing the power table, energy table, and charts.

Run (from project root):
    python demo_pv_model.py
"""
from pathlib import Path

import pandas as pd

from core.pv_model import (
    get_pv_power_table,
    get_pv_energy_table,
    calculate_pv_surplus,
    plot_pv_power_profile,
    plot_pv_energy_by_period,
)

# Model parameters (see core/pv_model.py for sourcing) 
PV_CAPACITY_MW = 47.5      # actual DHD plant installed capacity (can be replaced)
TEMP_COEFF = -0.0034       # typical crystalline silicon panel value (can be replaced)
LOSS_FACTOR = 0.95

INPUT_PATH = Path("outputs/processed/pv_30min_clean.csv")
TABLE_DIR = Path("outputs/processed")
METRIC_DIR = Path("outputs/metrics")
FIGURE_DIR = Path("outputs/figures")


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"{INPUT_PATH} not found - run core/run_pipeline.py first "
            "to generate the processed data."
        )

    print(f"Reading real data from {INPUT_PATH} ...")
    df = pd.read_csv(INPUT_PATH)

    # 1. PV power table
    power_table = get_pv_power_table(
        df, pv_capacity=PV_CAPACITY_MW, temp_coeff=TEMP_COEFF, loss_factor=LOSS_FACTOR,
    )
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    power_out = TABLE_DIR / "pv_power_table.csv"
    power_table.to_csv(power_out, index=False)
    print(f"  [OK] PV power table       -> {power_out}  ({len(power_table)} rows)")

    # 2. PV energy table, daily + monthly
    METRIC_DIR.mkdir(parents=True, exist_ok=True)
    daily_energy = get_pv_energy_table(power_table, freq="D")
    daily_out = METRIC_DIR / "pv_energy_daily.csv"
    daily_energy.to_csv(daily_out, index=False)
    print(f"  [OK] PV energy table (day)   -> {daily_out}  ({len(daily_energy)} rows)")

    monthly_energy = get_pv_energy_table(power_table, freq="M")
    monthly_out = METRIC_DIR / "pv_energy_monthly.csv"
    monthly_energy.to_csv(monthly_out, index=False)
    print(f"  [OK] PV energy table (month) -> {monthly_out}  ({len(monthly_energy)} rows)")

    # 3. PV surplus/deficit vs load
    # DEMO ONLY: no real "load" column in the processed data yet - using a
    # placeholder constant load. Replace with the real load column once
    # the Data Lead adds it.
    temp_load_mw = 25.0
    surplus, deficit = calculate_pv_surplus(power_table["pv_power_calc"], temp_load_mw)
    n_surplus = int((surplus > 0).sum())
    n_deficit = int((deficit > 0).sum())
    print(f"  [DEMO] PV surplus in {n_surplus} cycles / deficit in {n_deficit} cycles "
          f"(placeholder constant load of {temp_load_mw} MW)")

    # 4. Charts
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    profile_out = FIGURE_DIR / "pv_power_profile.png"
    plot_pv_power_profile(power_table, profile_out)
    print(f"  [OK] Power profile chart  -> {profile_out}")

    daily_chart_out = FIGURE_DIR / "pv_energy_daily.png"
    plot_pv_energy_by_period(daily_energy, daily_chart_out, freq="D")
    print(f"  [OK] Daily energy chart   -> {daily_chart_out}")

    monthly_chart_out = FIGURE_DIR / "pv_energy_monthly.png"
    plot_pv_energy_by_period(monthly_energy, monthly_chart_out, freq="M")
    print(f"  [OK] Monthly energy chart -> {monthly_chart_out}")

    total_energy = daily_energy["pv_energy"].sum()
    print(f"\nTotal simulated PV energy for the period: {total_energy:,.1f} MWh")


if __name__ == "__main__":
    main()