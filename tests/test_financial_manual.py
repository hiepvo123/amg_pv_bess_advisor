print("Starting test...")

from core.modeling_section.financial_model import FinancialModel

model = FinancialModel(
    capex=43e9,
    opex=500e6,
    annual_revenue=9e9,
    discount_rate=0.1,
    project_life=20,
)

print("Model created")

results = model.calculate_financial_metrics()

print(results)

print("Finished")