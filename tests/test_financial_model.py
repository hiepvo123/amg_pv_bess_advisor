import sys
from pathlib import Path
import pandas as pd

# --------------------------------------------------
# Project Path
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.modeling_section.financial_model import (
    FinancialModel,
    load_financial_config
)

# --------------------------------------------------
# Load Configuration
# --------------------------------------------------

cfg = load_financial_config("data/financial_config.json")

# --------------------------------------------------
# Load PV Prediction
# --------------------------------------------------

power_df = pd.read_csv(
    "outputs/processed/power_predictions.csv"
)

energy_mwh = (
    power_df["pred_RandomForest"] * 0.5
).sum()

days = len(power_df) / 48

annual_pv_energy_mwh = energy_mwh * 365 / days
annual_pv_energy_kwh = annual_pv_energy_mwh * 1000

# --------------------------------------------------
# BESS Energy
# --------------------------------------------------


# --------------------------------------------------
# Build Model
# --------------------------------------------------
annual_bess_energy = 2774000
model = FinancialModel(

    pv_capex=cfg["pv_capex"],
    bess_capex=cfg["bess_capex"],
    inverter_capex=cfg["inverter_capex"],
    other_capex=cfg["other_capex"],

    pv_opex=cfg["pv_opex"],
    bess_opex=cfg["bess_opex"],

    electricity_price=cfg["electricity_price"],

    discount_rate=cfg["discount_rate"],
    project_life=cfg["project_life"],

    annual_pv_energy=annual_pv_energy_kwh,
    annual_bess_energy=annual_bess_energy,

    loan_fraction=cfg["loan_fraction"],
    loan_interest_rate=cfg["loan_interest_rate"],
    loan_term=cfg["loan_term"],

    tax_rate=cfg["tax_rate"],
    inflation_rate=cfg["inflation_rate"],

    price_growth_rate=cfg["price_growth_rate"],

    pv_degradation_rate=cfg["pv_degradation_rate"],
    battery_degradation_rate=cfg["battery_degradation_rate"],

    battery_replacement_cost=cfg["battery_replacement_cost"],
    battery_replacement_year=cfg["battery_replacement_year"],

    inverter_replacement_cost=cfg["inverter_replacement_cost"],
    inverter_replacement_year=cfg["inverter_replacement_year"],

    salvage_value=cfg["salvage_value"],

    depreciation_years=cfg["depreciation_years"],

    depreciation_method="SL"
)

# --------------------------------------------------
# BASIC MODEL TEST
# --------------------------------------------------

print("\n")
print("=" * 80)
print("FINANCIAL MODEL TEST")
print("=" * 80)

print("\nModel Information")
print("-" * 80)

print(f"Total CAPEX           : {model.capex:,.0f}")
print(f"Loan Amount           : {model.capex*model.loan_fraction:,.0f}")
print(f"Equity Investment     : {model.capex*(1-model.loan_fraction):,.0f}")

print(f"Annual PV Energy      : {annual_pv_energy_kwh:,.2f} kWh")
print(f"Annual BESS Energy    : {annual_bess_energy:,.2f} kWh")

print(f"Year 1 Revenue        : {model.get_revenue_for_year(1):,.0f}")
print(f"Year 1 OPEX           : {model.get_opex_for_year(1):,.0f}")

print(f"Year 1 Depreciation   : {model.get_depreciation(1):,.0f}")

print(f"Year 1 Interest       : {model.get_interest_payment(1):,.0f}")

print(f"Year 1 Principal      : {model.get_principal_payment(1):,.0f}")

# --------------------------------------------------
# CASHFLOW
# --------------------------------------------------

cashflow = model.calculate_cash_flow()

print("\n")
print("=" * 80)
print("FIRST 10 YEARS CASHFLOW")
print("=" * 80)

print(cashflow.head(10))

print("\n")
print("=" * 80)
print("LAST 5 YEARS")
print("=" * 80)

print(cashflow.tail())

# --------------------------------------------------
# FINANCIAL METRICS
# --------------------------------------------------

print("\n")
print("=" * 80)
print("FINANCIAL METRICS")
print("=" * 80)

print(f"NPV      : {model.calculate_npv():,.2f}")

print(f"IRR      : {model.calculate_irr()*100:.2f}%")

print(f"Payback  : {model.calculate_payback():.2f} years")

print(f"LCOE     : {model.calculate_lcoe():,.2f}")

print(f"LCOS     : {model.calculate_lcos():,.2f}")

# --------------------------------------------------
# EXPORT
# --------------------------------------------------

cashflow.to_csv(
    "outputs/cashflow.csv",
    index=False
)

pd.DataFrame(
    model.loan_schedule
).T.to_csv(
    "outputs/loan_schedule.csv"
)

model.export_cashflow_excel(
    "outputs/cashflow.xlsx"
)

model.plot_cumulative_cashflow(
    "outputs/figures/cumulative_cashflow.png"
)

print("\n")
print("=" * 80)
print("EXPORT COMPLETED")
print("=" * 80)