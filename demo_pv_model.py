"""
demo_pv_model.py

Runs the PV module (core/pv_model.py) on the project's real data,
produces the power table, energy table, charts, and the rule engine
input file (03_bess_rule_input.csv).

Run (from project root):
    python demo_pv_model.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

from core.pv_model import (
    get_pv_power_table,
    get_pv_energy_table,
    calculate_pv_surplus,
    plot_pv_power_profile,
    plot_pv_energy_by_period,
)

# Model parameters
PV_CAPACITY_MW = 47.5
TEMP_COEFF     = -0.00410   # LONGi Solar LR6-72HV-340M (confirmed by AMG)
LOSS_FACTOR    = 0.95

INPUT_PATH = Path("outputs/processed/pv_30min_clean.csv")
TABLE_DIR  = Path("outputs/processed")
METRIC_DIR = Path("outputs/metrics")
FIGURE_DIR = Path("outputs/figures")


# Load profile from AMG scenario data

# 3 anchor values from AMG thesis data (110kV Ba Che - Ba Thuoc branch,
# Thanh Hoa province). Source: "Nghien cuu anh huong cua nguon nang luong
# tai tao toi luoi dien 110 kV tinh Thanh Hoa", Bang 1.2 va Bang 1.3.
# Note: This is STATIC scenario data, not a measured time series.
# A time-series load profile is built by interpolating between these
# three anchor points. Replace with real measured time series when available.
LOAD_MIN_MW   = 24.60    # night minimum load (scenario: Cuc tieu)
LOAD_NOON_MW  = 71.60    # typical noon load  (scenario: 12h ngay 16/4/2021)
LOAD_MAX_MW   = 156.70   # system maximum     (scenario: Cuc dai)

# Scenario table (saved as CSV for reference)
SCENARIOS = pd.DataFrame([
    {"scenario": "Cuc_dai",       "Pload_MW": 156.70, "Qload_MVAr": 68.03, "Sload_MVA": 170.83, "cosphi": 0.92},
    {"scenario": "Cuc_tieu",      "Pload_MW":  24.60, "Qload_MVAr":  9.85, "Sload_MVA":  26.50, "cosphi": 0.93},
    {"scenario": "12h_16Apr2021", "Pload_MW":  71.60, "Qload_MVAr": 29.55, "Sload_MVA":  77.46, "cosphi": 0.92},
])


def build_load_profile(timestamps: pd.DatetimeIndex) -> np.ndarray:
    """
    Build a 30-min load time series by interpolating between the three
    AMG scenario anchor points.

    Daily profile construction:
      - 03:00 -> LOAD_MIN_MW   (overnight trough)
      - 09:00 -> LOAD_NOON_MW  (morning ramp)
      - 12:00 -> LOAD_NOON_MW  (noon plateau)
      - 18:00 -> LOAD_MAX_MW * 0.70  (evening peak, scaled below absolute max)
      - 22:00 -> LOAD_NOON_MW * 0.60 (late-night ramp down)
      - 03:00 -> LOAD_MIN_MW   (back to trough)

    The absolute max (156.70 MW) represents an extreme scenario across all
    4 substations simultaneously; the daily evening peak is set to 70% of
    that to reflect a realistic daily operating level.
    """
    hour = timestamps.hour + timestamps.minute / 60.0

    # Control points (hour, fraction-of-range)
    # fraction = (P - min) / (max - min) so we can work in [0, 1]
    peak_mw     = LOAD_MAX_MW * 0.70           # realistic daily peak ~109.7 MW
    rng_mw      = LOAD_MAX_MW - LOAD_MIN_MW    # 132.1 MW span

    def frac(p):
        return (p - LOAD_MIN_MW) / rng_mw

    ctrl_h = np.array([ 0,    3,    6,    9,             12,            15,            18,           21,           24])
    ctrl_f = np.array([frac(LOAD_MIN_MW*1.1),
                       frac(LOAD_MIN_MW),
                       frac(LOAD_MIN_MW*1.3),
                       frac(LOAD_NOON_MW*0.90),
                       frac(LOAD_NOON_MW),
                       frac(LOAD_NOON_MW*1.10),
                       frac(peak_mw),
                       frac(LOAD_NOON_MW*0.85),
                       frac(LOAD_MIN_MW*1.1)])

    # Interpolate, then map back to MW
    fraction = np.interp(hour, ctrl_h, ctrl_f)
    profile  = LOAD_MIN_MW + fraction * rng_mw

    # Day-to-day variation: ±5% random noise, seed fixed for reproducibility
    rng   = np.random.default_rng(seed=42)
    noise = rng.normal(1.0, 0.05, len(timestamps))
    return np.clip(profile * noise, LOAD_MIN_MW * 0.9, LOAD_MAX_MW)


# Main 

def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"{INPUT_PATH} not found — run core/run_pipeline.py first."
        )

    print(f"Reading real PV data from {INPUT_PATH} ...")
    df = pd.read_csv(INPUT_PATH)

    # 1. PV power table
    power_table = get_pv_power_table(
        df, pv_capacity=PV_CAPACITY_MW, temp_coeff=TEMP_COEFF, loss_factor=LOSS_FACTOR,
    )
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    power_out = TABLE_DIR / "pv_power_table.csv"
    power_table.to_csv(power_out, index=False)
    print(f"  [OK] PV power table           -> {power_out}  ({len(power_table)} rows)")

    # 2. PV energy tables
    METRIC_DIR.mkdir(parents=True, exist_ok=True)
    daily_energy   = get_pv_energy_table(power_table, freq="D")
    monthly_energy = get_pv_energy_table(power_table, freq="M")
    daily_energy.to_csv(  METRIC_DIR / "pv_energy_daily.csv",   index=False)
    monthly_energy.to_csv(METRIC_DIR / "pv_energy_monthly.csv", index=False)
    print(f"  [OK] PV energy table (day)    -> {METRIC_DIR / 'pv_energy_daily.csv'}")
    print(f"  [OK] PV energy table (month)  -> {METRIC_DIR / 'pv_energy_monthly.csv'}")

    # 3. AMG scenario table (static reference)
    scenarios_out = METRIC_DIR / "02_load_scenarios_amg.csv"
    SCENARIOS.to_csv(scenarios_out, index=False)
    print(f"  [OK] AMG load scenarios       -> {scenarios_out}  (3 scenarios, real data)")

    # 4. Load time series from AMG anchor points + PV surplus/deficit
    timestamps = pd.DatetimeIndex(pd.to_datetime(power_table["datetime"]))
    load_mw    = build_load_profile(timestamps)
    surplus_mw, deficit_mw = calculate_pv_surplus(power_table["pv_power_calc"], load_mw)

    n_surplus = int((surplus_mw > 0).sum())
    n_deficit = int((deficit_mw > 0).sum())
    print(f"  [SCENARIO-BASED LOAD] surplus {n_surplus} cycles / deficit {n_deficit} cycles")
    print(f"    Load range: {load_mw.min():.1f} - {load_mw.max():.1f} MW")
    print(f"    Anchored on real AMG data: min={LOAD_MIN_MW}, noon={LOAD_NOON_MW}, max={LOAD_MAX_MW} MW")

    # 5. Rule engine input file (03_bess_rule_input.csv)
    # This is the PV module's handoff to the Rule Engine.
    rule_input = pd.DataFrame({
        "timestamp":      power_table["datetime"],
        "P_PV_MW":        power_table["pv_power_calc"].round(4),
        "P_load_MW":      np.round(load_mw, 4),
        "P_surplus_MW":   np.round(surplus_mw, 4),
        "P_deficit_MW":   np.round(deficit_mw, 4),
        "load_source":    "AMG_SCENARIO_INTERPOLATED",
    })
    rule_out = Path("outputs") / "03_bess_rule_input.csv"
    rule_out.parent.mkdir(parents=True, exist_ok=True)
    rule_input.to_csv(rule_out, index=False)
    print(f"  [OK] Rule engine input file   -> {rule_out}  ({len(rule_input)} rows)")

    # 6. Charts
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plot_pv_power_profile(power_table, FIGURE_DIR / "pv_power_profile.png")
    print(f"  [OK] Power profile chart      -> {FIGURE_DIR / 'pv_power_profile.png'}")
    plot_pv_energy_by_period(daily_energy,   FIGURE_DIR / "pv_energy_daily.png",   freq="D")
    print(f"  [OK] Daily energy chart       -> {FIGURE_DIR / 'pv_energy_daily.png'}")
    plot_pv_energy_by_period(monthly_energy, FIGURE_DIR / "pv_energy_monthly.png", freq="M")
    print(f"  [OK] Monthly energy chart     -> {FIGURE_DIR / 'pv_energy_monthly.png'}")

    total_energy = daily_energy["pv_energy"].sum()
    print(f"\nTotal simulated PV energy for the period: {total_energy:,.1f} MWh")
    print(f"Panel model : LONGi Solar LR6-72HV-340M  |  TEMP_COEFF = {TEMP_COEFF}")


if __name__ == "__main__":
    main()