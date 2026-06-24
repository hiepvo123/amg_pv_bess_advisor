import sys
from pathlib import Path
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

print("Project root:", PROJECT_ROOT)
from core.modeling_section.financial_model import FinancialModel

# --------------------------------------------------
# Load model prediction output
# --------------------------------------------------

pred_df = pd.read_csv(
    "outputs/processed/power_predictions.csv"
)

# --------------------------------------------------
# Energy calculation
# --------------------------------------------------
# 30-minute interval
# Energy(MWh) = Power(MW) × 0.5 h
# --------------------------------------------------

energy_mwh = (
    pred_df["pred_RandomForest"] * 0.5
).sum()

days_in_dataset = len(pred_df) / 48

annual_energy_mwh = (
    energy_mwh * 365 / days_in_dataset
)

annual_energy_kwh = (
    annual_energy_mwh * 1000
)

print(f"Dataset Energy: {energy_mwh:,.2f} MWh")
print(f"Annual Energy: {annual_energy_mwh:,.2f} MWh")

# --------------------------------------------------
# Revenue
# --------------------------------------------------

electricity_price = 1800

annual_revenue = (
    annual_energy_kwh *
    electricity_price
)

print(
    f"Annual Revenue: {annual_revenue:,.0f} VND"
)

# --------------------------------------------------
# Financial Model
# --------------------------------------------------

model = FinancialModel(
    capex=600e9,
    opex=6e9,
    annual_revenue=annual_revenue,
    discount_rate=0.10,
    project_life=20,
    annual_pv_energy=annual_energy_kwh,
    annual_bess_energy=10e6
)

results = model.calculate_financial_metrics()

print("\n===== FINANCIAL RESULTS =====\n")

for k, v in results.items():
    print(f"{k}: {v:,.2f}")


# Export outputs
model.export_cashflow_excel(
    "outputs/cashflowriel.xlsx"
)

model.plot_cumulative_cashflow(
    "outputs/figures/cumulative_cashflow.png"
)