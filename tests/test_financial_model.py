from core.modeling_section.financial_model import FinancialModel
def test_npv_positive():
    model = FinancialModel(
        capex=1e9,
        opex=1e7,
        annual_revenue=2e8,
        discount_rate=0.1,
        project_life=20 
    )

    assert model.calculate_npv() > 0