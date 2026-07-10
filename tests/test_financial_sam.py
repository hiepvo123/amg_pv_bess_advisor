"""Focused regression tests for SAM-style financial-model features."""

import numpy as np
import pandas as pd
import pytest

from core.financial_model import FinancialModel


@pytest.fixture
def model_kwargs():
    timestamps = pd.date_range("2025-01-01", periods=48, freq="30min")
    return {
        "pv_capex": 10_000_000,
        "bess_capex": 5_000_000,
        "pv_opex": 100_000,
        "bess_opex": 50_000,
        "discount_rate": 0.10,
        "project_life": 5,
        "pv_result": pd.DataFrame({
            "datetime": timestamps,
            "pv_power_calc": np.full(48, 1.0),
        }),
        "bess_result": pd.DataFrame({
            "datetime": timestamps,
            "energy_out_kwh": np.full(48, 20.0),
        }),
        "battery_replacement_year": 3,
        "battery_replacement_cost": 2_000_000,
        "depreciation_years": 5,
        "electricity_price": 1_000,
        "loan_fraction": 0,
        "tax_rate": 0.20,
    }


def test_revenue_is_itemized_for_capacity_and_pbi(model_kwargs):
    model = FinancialModel(
        **model_kwargs,
        capacity_payment=500_000,
        production_incentive_rate=20,
        production_incentive_years=2,
    )
    year_one = model.revenue_schedule.iloc[0]

    assert year_one["Capacity Revenue (VND)"] == pytest.approx(500_000)
    assert year_one["Production Incentive (VND)"] == pytest.approx(
        year_one["Total Energy (kWh)"] * 20
    )
    assert year_one["Revenue (VND)"] == pytest.approx(
        year_one["Energy Sales Revenue (VND)"]
        + year_one["Capacity Revenue (VND)"]
        + year_one["Production Incentive (VND)"]
    )


def test_itc_reduces_tax_basis_and_carries_forward(model_kwargs):
    model = FinancialModel(**model_kwargs, investment_tax_credit_rate=0.30)
    cash_flow = model.calculate_cash_flow()
    year_one = cash_flow.loc[cash_flow["Year"] == 1].iloc[0]

    credit = model.capex * 0.30
    assert model.investment_tax_credit == pytest.approx(credit)
    assert year_one["ITC Generated (VND)"] == pytest.approx(credit)
    assert year_one["ITC Applied (VND)"] <= year_one["Taxable Income (VND)"] * model.tax_rate
    assert model.depreciation_schedule.iloc[0]["Base Depreciation (VND)"] == pytest.approx(
        (model.capex - credit * 0.50) / model.depreciation_years
    )


def test_battery_replacement_restarts_its_degradation_curve(model_kwargs):
    model = FinancialModel(**model_kwargs, battery_degradation_rate=0.10)
    energy = model.energy_schedule.set_index("Year")["BESS Energy (kWh)"]

    assert energy.loc[2] < energy.loc[1]
    assert energy.loc[3] == pytest.approx(energy.loc[1])


def test_terminal_proceeds_and_project_cash_flow_are_unlevered(model_kwargs):
    model = FinancialModel(**model_kwargs, salvage_value=1_000_000)
    cash_flow = model.calculate_cash_flow()
    terminal = cash_flow.iloc[-1]

    assert terminal["Salvage (VND)"] == pytest.approx(1_000_000)
    assert cash_flow.iloc[0]["Project Cash Flow (VND)"] == pytest.approx(
        -(model.capex + model.idc)
    )
    summary = model.calculate_financial_metrics()
    assert {"Total Project Cost (VND)", "Investment Tax Credit (VND)", "Project NPV (VND)"} <= set(summary)
