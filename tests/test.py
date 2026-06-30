"""
Test Financial Model

Workflow:
1. Run/load PV simulation results.
2. (Optional) Run/load BESS simulation results.
3. Load financial configuration.
4. Create FinancialModel.
5. Print cash flow.
6. Print financial metrics.
7. Compare with SAM outputs.
"""
import sys
from pathlib import Path
import json
import pandas as pd

# =====================================================
# CHANGE THESE IMPORTS TO MATCH YOUR PROJECT
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.modeling_section.financial_model import (
    FinancialModel,
    load_financial_config
)

from core.bess_model import (
     BESSModelParams,
     simulate_bess_series
)
# Create BESS parameters
params = BESSModelParams()

# One year (30-minute intervals)
n = 48 * 365

# Battery idle by default
bess_cmd_series = pd.Series(["IDLE"] * n)

# Power request = 0 kW
bess_power_series = pd.Series([0.0] * n)

# Example: charge from 10:00–12:00 every day
for day in range(365):

    start = day * 48 + 20

    for i in range(start, start + 4):
        bess_cmd_series.iloc[i] = "CHARGE"
        bess_power_series.iloc[i] = 4000

# Example: discharge from 18:00–20:00 every day
for day in range(365):

    start = day * 48 + 36

    for i in range(start, start + 4):
        bess_cmd_series.iloc[i] = "DISCHARGE"
        bess_power_series.iloc[i] = 4000

# Run simulation
bess_result = simulate_bess_series(
    bess_cmd_series,
    bess_power_series,
    params
)

# from core.modeling_section.pv_model import PVModel
# from core.modeling_section.bess_model import BESSModel

# =====================================================
# LOAD PV RESULTS
# =====================================================

# Option 1: Load previously generated results
pv_result = pd.read_csv("outputs/processed/pv_power_table.csv")

# If datetime column does not exist
if "datetime" not in pv_result.columns:

    pv_result["datetime"] = pd.date_range(
        start="2024-01-01",
        periods=len(pv_result),
        freq="30min"
    )

# If the column name differs
if "pv_power_calc" not in pv_result.columns:

    # Example:
    # pred_RandomForest
    # pv_power
    # power
    pv_result = pv_result.rename(
        columns={
            "pred_RandomForest": "pv_power_calc"
        }
    )

# =====================================================
# LOAD CONFIG
# =====================================================

config = load_financial_config(
    "data/financial_config.json"
)

# =====================================================
# CREATE MODEL
# =====================================================

model = FinancialModel(

    # CAPEX
    pv_capex=config["pv_capex"],
    inverter_capex=config["inverter_capex"],
    other_capex=config["other_capex"],
    bess_capex=config["bess_capex"],

    # OPEX
    pv_opex=config["pv_opex"],
    bess_opex=config["bess_opex"],

    # Project
    discount_rate=config["discount_rate"],
    project_life=config["project_life"],

    # Simulation results
    pv_result=pv_result,
    bess_result=bess_result,
    
    electricity_price=config["electricity_price"],

    # Replacement
    battery_replacement_cost=config["battery_replacement_cost"],
    battery_replacement_year=config["battery_replacement_year"],

    inverter_replacement_cost=config["inverter_replacement_cost"],
    inverter_replacement_year=config["inverter_replacement_year"],

    battery_degradation_rate=config["battery_degradation_rate"],
    pv_degradation_rate=config["pv_degradation_rate"],

    # Escalation
    price_growth_rate=config["price_growth_rate"],
    opex_growth_rate=config.get("opex_growth_rate", 0.02),

    # Financing
    loan_fraction=config["loan_fraction"],
    loan_interest_rate=config["loan_interest_rate"],
    loan_term=config["loan_term"],

    tax_rate=config["tax_rate"],
    inflation_rate=config["inflation_rate"],

    depreciation_years=config["depreciation_years"],

    salvage_value=config["salvage_value"],
)

# =====================================================
# CASH FLOW
# =====================================================

cashflow = model.calculate_cash_flow()

print("\n")
print("=" * 100)
print("CASH FLOW")
print("=" * 100)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

print(cashflow)

# =====================================================
# FINANCIAL METRICS
# =====================================================

metrics = model.calculate_financial_metrics()

print("\n")
print("=" * 100)
print("FINANCIAL METRICS")
print("=" * 100)

for key, value in metrics.items():

    if isinstance(value, float):

        print(f"{key:<35}: {value:,.2f}")

    else:

        print(f"{key:<35}: {value}")

# =====================================================
# ENERGY SUMMARY
# =====================================================

print("\n")
print("=" * 100)
print("ENERGY SUMMARY")
print("=" * 100)

print(f"Annual PV Energy     : {model.pv_energy:,.2f} MWh")
print(f"Annual BESS Energy   : {model.bess_energy:,.2f} kWh")

# =====================================================
# SAM COMPARISON
# =====================================================

# Replace these values with the outputs exported from SAM

sam = {

    "NPV (VND)": 0,

    "IRR (%)": 0,

    "Payback (Years)": 0,

    "LCOE (VND/kWh)": 0,

    "LCOS (VND/kWh)": 0,

}

print("\n")
print("=" * 100)
print("FINANCIAL MODEL vs SAM")
print("=" * 100)

print(
    f"{'Metric':35}"
    f"{'Financial Model':>20}"
    f"{'SAM':>20}"
    f"{'Difference':>20}"
)

print("-" * 95)

for key in sam:

    model_value = metrics[key]

    sam_value = sam[key]

    difference = model_value - sam_value

    print(
        f"{key:35}"
        f"{model_value:20,.2f}"
        f"{sam_value:20,.2f}"
        f"{difference:20,.2f}"
    )

# =====================================================
# OPTIONAL YEAR-BY-YEAR COMPARISON
# =====================================================

"""
If you export SAM's annual cash flow to CSV,
you can compare automatically.

Example:

sam_cashflow = pd.read_csv("outputs/sam_cashflow.csv")

comparison = pd.DataFrame({
    "Year": cashflow["Year"],
    "Model Revenue": cashflow["Revenue (VND)"],
    "SAM Revenue": sam_cashflow["Revenue"],
    "Difference": cashflow["Revenue (VND)"] - sam_cashflow["Revenue"]
})

print(comparison)
"""

print("\n")
print("=" * 100)
print("TEST COMPLETED")
print("=" * 100)