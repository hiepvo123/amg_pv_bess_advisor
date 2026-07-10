"""
Test / demo script for financial_model.py

Since we don't have real PV/BESS simulation output to plug in, this script
generates synthetic half-hourly PV and BESS profiles for one representative
year, then runs them through FinancialModel end-to-end: build the project,
print the SAM-style summary (including DSCR), and export the full cash flow
workbook + cumulative cash flow chart.

Replace `build_synthetic_pv_result()` / `build_synthetic_bess_result()` with
your real simulation outputs, and PROJECT_PARAMS below with your real project
assumptions, when you're ready to run this on an actual project.
"""

import os
import numpy as np
import pandas as pd

from core.financial_model import FinancialModel

OUTPUT_DIR = "/mnt/user-data/outputs"
EXCEL_PATH = os.path.join(OUTPUT_DIR, "cashflow_results.xlsx")
CHART_PATH = os.path.join(OUTPUT_DIR, "figures", "cumulative_cashflow.png")


# ---------------------------------------------------------------------------
# Synthetic PV / BESS profiles (SAMPLE DATA -- replace with real simulation
# results before using this for an actual project)
# ---------------------------------------------------------------------------

def build_synthetic_pv_result(days=365, capacity_mw=5.0, start="2025-01-01", seed=42):
    """
    Half-hourly PV power (MW) for `days` days: a daylight bell curve
    (roughly 6am-6pm) with day-to-day cloud variability. Matches the
    columns FinancialModel.initialize_energy_inputs() expects:
    'datetime' and 'pv_power_calc'.
    """
    idx = pd.date_range(start, periods=days * 48, freq="30min")
    hours = idx.hour + idx.minute / 60

    daylight_shape = np.clip(np.sin(np.pi * (hours - 6) / 12), 0, None)

    rng = np.random.default_rng(seed)
    daily_cloud_factor = np.repeat(rng.uniform(0.75, 1.0, days), 48)

    pv_power_mw = capacity_mw * daylight_shape * daily_cloud_factor

    return pd.DataFrame({"datetime": idx, "pv_power_calc": pv_power_mw})


def build_synthetic_bess_result(days=365, daily_discharge_mwh=2.0, start="2025-01-01"):
    """
    Half-hourly BESS discharge energy (kWh) for `days` days: battery
    discharges evenly across the evening peak window (18:00-22:00).
    Matches the column FinancialModel.initialize_energy_inputs() expects:
    'energy_out_kwh'.
    """
    idx = pd.date_range(start, periods=days * 48, freq="30min")
    hours = idx.hour + idx.minute / 60

    peak_mask = (hours >= 18) & (hours < 22)
    intervals_in_peak = peak_mask.sum() / days  # per day

    energy_per_interval_kwh = (daily_discharge_mwh * 1000) / intervals_in_peak
    energy_out_kwh = np.where(peak_mask, energy_per_interval_kwh, 0.0)

    return pd.DataFrame({"datetime": idx, "energy_out_kwh": energy_out_kwh})


# ---------------------------------------------------------------------------
# Example project assumptions (SAMPLE DATA -- replace with your real numbers)
# ---------------------------------------------------------------------------

PROJECT_PARAMS = dict(
    # CAPEX (VND)
    pv_capex=50_000_000_000,
    bess_capex=20_000_000_000,
    inverter_capex=3_000_000_000,
    other_capex=2_000_000_000,

    # OPEX (VND, Year 1)
    pv_opex=500_000_000,
    bess_opex=200_000_000,
    insurance_cost=150_000_000,
    property_tax=100_000_000,
    land_lease_cost=300_000_000,
    variable_opex_rate=5,          # VND per kWh of total throughput

    # Revenue
    electricity_price=1_800,       # VND/kWh
    price_growth_rate=0.01,

    # Escalation / macro
    opex_growth_rate=0.025,
    inflation_rate=0.03,
    discount_rate=0.10,

    # Project
    project_life=25,
    pv_degradation_rate=0.005,
    battery_degradation_rate=0.02,
    salvage_value=5_000_000_000,

    # Financing
    loan_fraction=0.70,
    loan_interest_rate=0.09,
    loan_term=15,
    tax_rate=0.20,

    # Construction period / IDC
    construction_period_years=1,
    idc_rate=0.09,

    # Depreciation -- MACRS 10-year class life (demonstrates the fixed
    # MACRS-table-selection logic: depreciation_years must match a
    # supported class life)
    depreciation_years=10,
    depreciation_method="MACRS",

    # Replacements -- multiple events (demonstrates list-based
    # battery/inverter replacement years/costs)
    battery_replacement_year=[10, 20],
    battery_replacement_cost=[8_000_000_000, 9_000_000_000],
    inverter_replacement_year=[8, 16, 24],
    inverter_replacement_cost=1_500_000_000,  # scalar -> applied to every event

    # DSCR
    min_dscr_threshold=1.25,
)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pv_result = build_synthetic_pv_result()
    bess_result = build_synthetic_bess_result()

    model = FinancialModel(
        pv_result=pv_result,
        bess_result=bess_result,
        **PROJECT_PARAMS,
    )

    # ---- Console summary (SAM-style) ----
    model.print_summary()

    # ---- DSCR detail beyond what print_summary shows ----
    dscr = model.calculate_dscr_summary()
    print("\nDSCR by year (loan term only):")
    for year, value in dscr["DSCR by Year"].items():
        flag = "" if value >= model.min_dscr_threshold else "  <-- below threshold"
        print(f"  Year {year:>2}: {value:6.2f}x{flag}")

    # ---- Export full cash flow workbook ----
    model.export_cashflow_excel(filename=EXCEL_PATH)

    # ---- Export cumulative cash flow chart ----
    model.plot_cumulative_cashflow(filename=CHART_PATH)

    print(f"\nDone. Workbook: {EXCEL_PATH}")
    print(f"Done. Chart:    {CHART_PATH}")


if __name__ == "__main__":
    main()
