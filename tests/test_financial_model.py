"""
Test suite for FinancialModel (financial_model.py).

Run with:
    pytest test_financial_model.py -v

Covers:
    - Regression tests for the 4 bugs previously fixed:
        1. opex_schedule column name mismatch in calculate_cash_flow
        2. loan_schedule dict-vs-DataFrame access in calculate_cash_flow
        3. missing get_pv_energy_for_year() used by variable O&M
        4. discount-rate inconsistency between PV cost and PV energy
           in the LCOE calculation
    - General correctness of each schedule builder
    - Financial metrics (NPV, IRR, payback, LCOE, LCOS)
    - Input validation
    - Excel/chart export side effects
"""

import math
import matplotlib
matplotlib.use("Agg")  # headless-safe backend, must be set before pyplot use

import numpy as np
import pandas as pd
import numpy_financial as npf
import pytest

from core.financial_model import FinancialModel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pv_result():
    """
    One full day (48 half-hourly rows) of constant 1 MW PV output.
    -> simulated_energy = 48 * 0.5 = 24 MWh over 1 day
    -> annual_factor = 365 / 1 = 365
    -> self.pv_energy = 24 * 365 = 8760 (model's internal PV energy units)
    Kept deliberately simple/deterministic so schedule math is hand-checkable.
    """
    dt = pd.date_range("2025-01-01", periods=48, freq="30min")
    return pd.DataFrame({
        "datetime": dt,
        "pv_power_calc": np.full(48, 1.0),  # MW
    })


@pytest.fixture
def bess_result():
    """
    One full day (48 half-hourly rows) of constant 100 kWh discharge.
    -> simulated_bess_energy = 48 * 100 = 4800
    -> days = 48 / 48 = 1 -> annual_factor = 365
    -> self.bess_energy = 4800 * 365 = 1,752,000
    """
    dt = pd.date_range("2025-01-01", periods=48, freq="30min")
    return pd.DataFrame({
        "datetime": dt,
        "energy_out_kwh": np.full(48, 100.0),
    })


@pytest.fixture
def base_kwargs(pv_result, bess_result):
    """A reasonable, fully-specified set of constructor kwargs."""
    return dict(
        pv_capex=50_000_000_000,
        pv_opex=500_000_000,
        bess_opex=200_000_000,
        bess_capex=20_000_000_000,
        insurance_cost=100_000_000,
        property_tax=50_000_000,
        land_lease_cost=30_000_000,
        variable_opex_rate=5,          # VND/kWh - exercises get_pv_energy_for_year
        discount_rate=0.10,
        project_life=20,
        pv_result=pv_result,
        bess_result=bess_result,
        battery_replacement_cost=8_000_000_000,
        battery_replacement_year=10,
        inverter_replacement_cost=3_000_000_000,
        inverter_replacement_year=12,
        salvage_value=1_000_000_000,
        loan_fraction=0.70,
        loan_interest_rate=0.08,
        loan_term=15,                  # < project_life on purpose, see loan tests
        tax_rate=0.0825,
        inflation_rate=0.025,
        depreciation_years=20,
        depreciation_method="SL",
        electricity_price=1254,
    )


@pytest.fixture
def model(base_kwargs):
    return FinancialModel(**base_kwargs)


# ---------------------------------------------------------------------------
# Construction / capex split
# ---------------------------------------------------------------------------

class TestConstruction:

    def test_capex_is_sum_of_pv_and_bess(self, model, base_kwargs):
        assert model.capex == (
            base_kwargs["pv_capex"] + base_kwargs["bess_capex"]
        )

    def test_equity_and_debt_split(self, model, base_kwargs):
        metrics = model.calculate_financial_metrics()
        expected_debt = model.capex * base_kwargs["loan_fraction"]
        expected_equity = model.capex - expected_debt
        assert metrics["Debt Amount (VND)"] == pytest.approx(expected_debt)
        assert metrics["Equity Investment (VND)"] == pytest.approx(expected_equity)

    def test_pv_energy_annualization(self, model):
        # 48 rows * 1 MW * 0.5h = 24 MWh in 1 day -> * 365 = 8760
        assert model.pv_energy == pytest.approx(8760)

    def test_bess_energy_annualization(self, model):
        # 48 rows * 100 kWh = 4800 in 1 day -> * 365 = 1,752,000
        assert model.bess_energy == pytest.approx(1_752_000)

    def test_pv_energy_zero_when_no_pv_result(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["pv_result"] = None
        m = FinancialModel(**kwargs)
        assert m.pv_energy == 0

    def test_bess_energy_zero_when_no_bess_result(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["bess_result"] = None
        m = FinancialModel(**kwargs)
        assert m.bess_energy == 0

    def test_bess_annualization_is_robust_to_timestep(self, base_kwargs):
        """
        Regression test: annualization used to hard-code `len(df) / 48`,
        silently assuming 30-minute resolution. This checks that hourly
        (24 rows/day) data annualizes correctly instead of being treated
        as half a day.
        """
        kwargs = dict(base_kwargs)
        dt = pd.date_range("2025-01-01", periods=24, freq="1h")  # 1 full day, hourly
        kwargs["bess_result"] = pd.DataFrame({
            "datetime": dt,
            "energy_out_kwh": np.full(24, 50.0),  # 24 * 50 = 1200 kWh in 1 day
        })
        m = FinancialModel(**kwargs)
        # 1200 kWh/day * 365 = 438,000 kWh/year
        assert m.bess_energy == pytest.approx(438_000)

    def test_pv_annualization_is_robust_to_timestep(self, base_kwargs):
        """
        Regression test: PV energy conversion used to hard-code
        `sum(power) * 0.5`, silently assuming 30-minute resolution.
        This checks hourly (1h interval) PV data annualizes correctly.
        """
        kwargs = dict(base_kwargs)
        dt = pd.date_range("2025-01-01", periods=24, freq="1h")  # 1 full day, hourly
        kwargs["pv_result"] = pd.DataFrame({
            "datetime": dt,
            "pv_power_calc": np.full(24, 1.0),  # 1 MW * 24h = 24 MWh in 1 day
        })
        m = FinancialModel(**kwargs)
        # 1 (unit) * 24h = 24 (energy units)/day -> * 365 = 8760/year
        # (same magnitude as the 30-min fixture: resolution shouldn't matter)
        assert m.pv_energy == pytest.approx(24 * 365)


# ---------------------------------------------------------------------------
# Energy schedule
# ---------------------------------------------------------------------------

class TestEnergySchedule:

    def test_year_one_matches_undegraded_energy(self, model):
        row = model.energy_schedule.loc[model.energy_schedule["Year"] == 1].iloc[0]
        assert row["PV Energy (kWh)"] == pytest.approx(model.pv_energy)
        assert row["BESS Energy (kWh)"] == pytest.approx(model.bess_energy)

    def test_pv_degrades_year_over_year(self, model):
        sched = model.energy_schedule
        y1 = sched.loc[sched["Year"] == 1, "PV Energy (kWh)"].iloc[0]
        y2 = sched.loc[sched["Year"] == 2, "PV Energy (kWh)"].iloc[0]
        expected_y2 = model.pv_energy * (1 - model.pv_degradation_rate)
        assert y2 == pytest.approx(expected_y2)
        assert y2 < y1

    def test_bess_degrades_year_over_year(self, model):
        sched = model.energy_schedule
        y1 = sched.loc[sched["Year"] == 1, "BESS Energy (kWh)"].iloc[0]
        y2 = sched.loc[sched["Year"] == 2, "BESS Energy (kWh)"].iloc[0]
        expected_y2 = model.bess_energy * (1 - model.battery_degradation_rate)
        assert y2 == pytest.approx(expected_y2)
        assert y2 < y1

    def test_schedule_covers_full_project_life(self, model, base_kwargs):
        assert len(model.energy_schedule) == base_kwargs["project_life"]


# ---------------------------------------------------------------------------
# Revenue schedule
# ---------------------------------------------------------------------------

class TestRevenueSchedule:

    def test_year_one_revenue(self, model, base_kwargs):
        """
        Revenue must be earned on total dispatched energy (PV + BESS
        discharge), not PV energy alone. Regression test for the bug
        where build_revenue_schedule() ignored BESS Energy even though
        build_energy_schedule()'s own docstring says "Total Energy" is
        the intended source for the Revenue Schedule.
        """
        expected = (
            (model.pv_energy + model.bess_energy)
            * base_kwargs["electricity_price"]
        )
        assert model.get_revenue_for_year(1) == pytest.approx(expected)

    def test_revenue_excludes_bess_energy_is_a_bug_regression(self, model):
        """
        Explicit regression guard: revenue must NOT equal PV-only energy
        times price whenever BESS energy is present (that was the bug).
        """
        pv_only_revenue = model.pv_energy * model.electricity_price
        assert model.get_revenue_for_year(1) != pytest.approx(pv_only_revenue)

    def test_price_growth_applied(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["price_growth_rate"] = 0.05
        m = FinancialModel(**kwargs)
        price_y1 = m.revenue_schedule.loc[
            m.revenue_schedule["Year"] == 1, "Electricity Price (VND/kWh)"
        ].iloc[0]
        price_y2 = m.revenue_schedule.loc[
            m.revenue_schedule["Year"] == 2, "Electricity Price (VND/kWh)"
        ].iloc[0]
        assert price_y2 == pytest.approx(price_y1 * 1.05)


# ---------------------------------------------------------------------------
# Opex schedule  (regression test for bug #3: missing get_pv_energy_for_year)
# ---------------------------------------------------------------------------

class TestOpexSchedule:

    def test_variable_opex_does_not_raise(self, base_kwargs):
        """
        Previously: get_pv_energy_for_year() was called but never defined,
        raising AttributeError whenever variable_opex_rate != 0.
        """
        kwargs = dict(base_kwargs)
        kwargs["variable_opex_rate"] = 5
        m = FinancialModel(**kwargs)  # should not raise
        assert m.opex_schedule is not None

    def test_variable_opex_year_one_value(self, model, base_kwargs):
        expected_variable = base_kwargs["variable_opex_rate"] * model.pv_energy
        row = model.opex_schedule.loc[model.opex_schedule["Year"] == 1].iloc[0]
        assert row["Variable O&M (VND)"] == pytest.approx(expected_variable)

    def test_total_is_sum_of_components(self, model):
        row = model.opex_schedule.loc[model.opex_schedule["Year"] == 1].iloc[0]
        component_sum = (
            row["PV O&M (VND)"]
            + row["BESS O&M (VND)"]
            + row["Insurance (VND)"]
            + row["Property Tax (VND)"]
            + row["Land Lease (VND)"]
            + row["Variable O&M (VND)"]
        )
        assert row["Total O&M (VND)"] == pytest.approx(component_sum)

    def test_opex_grows_with_opex_growth_rate(self, model):
        sched = model.opex_schedule
        y1 = sched.loc[sched["Year"] == 1, "PV O&M (VND)"].iloc[0]
        y2 = sched.loc[sched["Year"] == 2, "PV O&M (VND)"].iloc[0]
        assert y2 == pytest.approx(y1 * (1 + model.opex_growth_rate))


# ---------------------------------------------------------------------------
# Loan schedule
# ---------------------------------------------------------------------------

class TestLoanSchedule:

    def test_loan_schedule_is_dict_keyed_by_year(self, model, base_kwargs):
        assert isinstance(model.loan_schedule, dict)
        assert set(model.loan_schedule.keys()) == set(
            range(1, base_kwargs["loan_term"] + 1)
        )

    def test_balance_fully_amortizes(self, model, base_kwargs):
        last_year = base_kwargs["loan_term"]
        assert model.loan_schedule[last_year]["balance"] == pytest.approx(0, abs=1)

    def test_payment_is_constant_across_years(self, model, base_kwargs):
        payments = {
            row["payment"] for row in model.loan_schedule.values()
        }
        # all annual payments should be identical (amortized loan)
        assert len(payments) == 1

    def test_interest_plus_principal_equals_payment(self, model):
        for row in model.loan_schedule.values():
            assert row["interest"] + row["principal"] == pytest.approx(row["payment"])

    def test_no_debt_gives_empty_schedule(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["loan_fraction"] = 0
        m = FinancialModel(**kwargs)
        assert m.loan_schedule == {}

    def test_get_interest_and_principal_helpers(self, model):
        assert model.get_interest_payment(1) == pytest.approx(
            model.loan_schedule[1]["interest"]
        )
        assert model.get_principal_payment(1) == pytest.approx(
            model.loan_schedule[1]["principal"]
        )
        # year beyond loan term -> helpers should return 0, not raise
        assert model.get_interest_payment(999) == 0
        assert model.get_principal_payment(999) == 0


# ---------------------------------------------------------------------------
# Depreciation schedule
# ---------------------------------------------------------------------------

class TestDepreciationSchedule:

    def test_straight_line_sums_to_asset_value(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["battery_replacement_cost"] = 0
        kwargs["inverter_replacement_cost"] = 0
        kwargs["depreciation_years"] = 20
        kwargs["project_life"] = 20
        m = FinancialModel(**kwargs)
        total_dep = m.depreciation_schedule["Total Depreciation (VND)"].sum()
        assert total_dep == pytest.approx(m.capex, rel=1e-6)

    def test_final_book_value_is_zero_for_fully_depreciated_asset(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["battery_replacement_cost"] = 0
        kwargs["inverter_replacement_cost"] = 0
        kwargs["depreciation_years"] = 20
        kwargs["project_life"] = 20
        m = FinancialModel(**kwargs)
        final_book_value = m.depreciation_schedule["Book Value (VND)"].iloc[-1]
        assert final_book_value == pytest.approx(0, abs=1)

    def test_macrs_rates_used_in_first_years(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["depreciation_method"] = "MACRS"
        kwargs["battery_replacement_cost"] = 0
        kwargs["inverter_replacement_cost"] = 0
        m = FinancialModel(**kwargs)
        y1 = m.depreciation_schedule.loc[
            m.depreciation_schedule["Year"] == 1, "Base Depreciation (VND)"
        ].iloc[0]
        assert y1 == pytest.approx(m.capex * 0.20)

    def test_unknown_depreciation_method_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["depreciation_method"] = "NOT_A_METHOD"
        with pytest.raises(ValueError):
            FinancialModel(**kwargs)


# ---------------------------------------------------------------------------
# Replacement schedule
# ---------------------------------------------------------------------------

class TestReplacementSchedule:

    def test_battery_replacement_lands_on_correct_year(self, model, base_kwargs):
        year = base_kwargs["battery_replacement_year"]
        cost = model.get_replacement_cost(year)
        assert cost == pytest.approx(base_kwargs["battery_replacement_cost"])

    def test_inverter_replacement_lands_on_correct_year(self, model, base_kwargs):
        year = base_kwargs["inverter_replacement_year"]
        row = model.replacement_schedule.loc[
            model.replacement_schedule["Year"] == year
        ].iloc[0]
        assert row["Inverter Replacement (VND)"] == pytest.approx(
            base_kwargs["inverter_replacement_cost"]
        )

    def test_no_replacement_cost_in_other_years(self, model, base_kwargs):
        other_year = 1
        assert other_year not in (
            base_kwargs["battery_replacement_year"],
            base_kwargs["inverter_replacement_year"],
        )
        assert model.get_replacement_cost(other_year) == 0


# ---------------------------------------------------------------------------
# Cash flow  (regression tests for bugs #1 and #2)
# ---------------------------------------------------------------------------

class TestCashFlow:

    def test_calculate_cash_flow_does_not_raise(self, model):
        """
        Previously: crashed with KeyError (opex column name) and then,
        once past that, AttributeError ('dict' has no attribute 'loc')
        on the loan_schedule lookup.
        """
        table = model.calculate_cash_flow()
        assert isinstance(table, pd.DataFrame)
        assert len(table) == model.life + 1  # year 0 + each project year

    def test_year_zero_is_negative_equity(self, model):
        row = model.calculate_cash_flow().iloc[0]
        expected_equity = -(model.capex * (1 - model.loan_fraction))
        assert row["Year"] == 0
        assert row["Equity Cash Flow (VND)"] == pytest.approx(expected_equity)

    def test_years_beyond_loan_term_have_zero_debt_service(self, model, base_kwargs):
        """
        Regression test for bug #2: years beyond loan_term used to blow up
        because the (fixed) dict-based lookup didn't exist yet. Now they
        should just show zero interest/principal and zero balance.
        """
        table = model.calculate_cash_flow()
        post_loan_years = table[table["Year"] > base_kwargs["loan_term"]]
        assert (post_loan_years["Interest (VND)"] == 0).all()
        assert (post_loan_years["Principal (VND)"] == 0).all()
        assert (post_loan_years["Loan Balance (VND)"] == 0).all()

    def test_opex_column_used_correctly(self, model):
        """
        Regression test for bug #1: EBITDA should reflect Total O&M, i.e.
        revenue minus the actual opex_schedule total, not a KeyError.
        """
        cash = model.calculate_cash_flow()
        year1_cash = cash.loc[cash["Year"] == 1].iloc[0]
        expected_opex = model.get_opex_for_year(1)
        assert year1_cash["OPEX (VND)"] == pytest.approx(expected_opex)
        assert year1_cash["EBITDA (VND)"] == pytest.approx(
            year1_cash["Revenue (VND)"] - expected_opex
        )

    def test_salvage_only_appears_in_final_year(self, model, base_kwargs):
        table = model.calculate_cash_flow()
        non_final = table[(table["Year"] != model.life) & (table["Year"] != 0)]
        assert (non_final["Salvage (VND)"] == 0).all()
        final = table[table["Year"] == model.life].iloc[0]
        assert final["Salvage (VND)"] == pytest.approx(
            base_kwargs["salvage_value"] * (1 - base_kwargs["tax_rate"])
        )


# ---------------------------------------------------------------------------
# Discount-rate consistency (regression test for bug #4)
# ---------------------------------------------------------------------------

class TestDiscountRateConsistency:

    def test_pv_cost_uses_real_discount_rate(self, base_kwargs):
        """
        Regression test for bug #4: present_value_total_pv_cost() used to
        discount at the *nominal* rate while present_value_total_pv_energy()
        discounts at the *real* rate, corrupting LCOE. Both should now use
        the real discount rate.
        """
        kwargs = dict(base_kwargs)
        kwargs["project_life"] = 3
        kwargs["inverter_replacement_cost"] = 0  # isolate opex-only PV cost
        kwargs["salvage_value"] = 0
        kwargs["discount_rate"] = 0.10
        kwargs["inflation_rate"] = 0.03  # ensures real_rate != nominal_rate
        m = FinancialModel(**kwargs)

        real_rate = m.real_discount_rate
        assert real_rate != pytest.approx(m.discount_rate)  # sanity: they differ

        expected = m.pv_capex + sum(
            m.pv_opex * (1 + m.opex_growth_rate) ** (year - 1) / (1 + real_rate) ** year
            for year in range(1, 4)
        )
        assert m.present_value_total_pv_cost() == pytest.approx(expected, rel=1e-9)

    def test_bess_cost_also_uses_real_discount_rate(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["project_life"] = 3
        kwargs["battery_replacement_cost"] = 0
        kwargs["discount_rate"] = 0.10
        kwargs["inflation_rate"] = 0.03
        m = FinancialModel(**kwargs)

        real_rate = m.real_discount_rate
        expected = m.bess_capex + sum(
            m.bess_opex * (1 + m.opex_growth_rate) ** (year - 1) / (1 + real_rate) ** year
            for year in range(1, 4)
        )
        assert m.present_value_total_bess_cost() == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Financial metrics: NPV / IRR / payback / LCOE / LCOS
# ---------------------------------------------------------------------------

class TestFinancialMetrics:

    def test_npv_matches_manual_sum(self, model):
        table = model.calculate_cash_flow()
        assert model.calculate_npv() == pytest.approx(
            table["Discounted Cash Flow (VND)"].sum()
        )

    def test_irr_matches_numpy_financial(self, model):
        table = model.calculate_cash_flow()
        expected_irr = npf.irr(table["Equity Cash Flow (VND)"])
        result = model.calculate_irr()
        if math.isnan(expected_irr):
            assert math.isnan(result)
        else:
            assert result == pytest.approx(expected_irr)

    def test_payback_within_project_life_or_none(self, model):
        payback = model.calculate_payback()
        assert payback is None or 0 <= payback <= model.life

    def test_lcoe_is_positive_when_pv_present(self, model):
        lcoe = model.calculate_lcoe()
        assert lcoe is not None
        assert lcoe > 0

    def test_lcoe_none_when_no_pv_energy(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["pv_result"] = None
        m = FinancialModel(**kwargs)
        assert m.calculate_lcoe() is None

    def test_lcos_is_positive_when_bess_present(self, model):
        lcos = model.calculate_lcos()
        assert lcos is not None
        assert lcos > 0

    def test_lcos_none_when_no_bess_energy(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["bess_result"] = None
        m = FinancialModel(**kwargs)
        assert m.calculate_lcos() is None

    def test_calculate_financial_metrics_has_expected_keys(self, model):
        metrics = model.calculate_financial_metrics()
        expected_keys = {
            "Total CAPEX (VND)", "Equity Investment (VND)", "Debt Amount (VND)",
            "Year 1 Revenue (VND)", "Year 1 OPEX (VND)", "NPV (VND)", "IRR (%)",
            "Payback (Years)", "LCOE (VND/kWh)", "LCOS (VND/kWh)",
        }
        assert expected_keys.issubset(metrics.keys())


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestValidation:

    def test_zero_capex_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["pv_capex"] = 0
        kwargs["bess_capex"] = 0
        with pytest.raises(AssertionError):
            FinancialModel(**kwargs)

    def test_negative_discount_rate_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["discount_rate"] = -0.01
        with pytest.raises(AssertionError):
            FinancialModel(**kwargs)

    def test_loan_fraction_over_one_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["loan_fraction"] = 1.5
        with pytest.raises(AssertionError):
            FinancialModel(**kwargs)

    def test_loan_fraction_negative_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["loan_fraction"] = -0.1
        with pytest.raises(AssertionError):
            FinancialModel(**kwargs)

    def test_tax_rate_over_one_raises(self, base_kwargs):
        kwargs = dict(base_kwargs)
        kwargs["tax_rate"] = 1.2
        with pytest.raises(AssertionError):
            FinancialModel(**kwargs)


# ---------------------------------------------------------------------------
# Export side effects (Excel + chart)
# ---------------------------------------------------------------------------

class TestExports:

    def test_export_cashflow_excel_creates_file(self, model, tmp_path):
        out_file = tmp_path / "cashflow.xlsx"
        model.export_cashflow_excel(filename=str(out_file))
        assert out_file.exists()
        assert out_file.stat().st_size > 0

    def test_export_cashflow_excel_has_expected_sheets(self, model, tmp_path):
        out_file = tmp_path / "cashflow.xlsx"
        model.export_cashflow_excel(filename=str(out_file))
        sheets = pd.ExcelFile(out_file).sheet_names
        for expected in ["Cash Flow", "Revenue", "OPEX", "Depreciation",
                          "Loan Schedule", "Replacement"]:
            assert expected in sheets

    def test_plot_cumulative_cashflow_creates_file(self, model, tmp_path):
        out_file = tmp_path / "figures" / "cashflow.png"
        model.plot_cumulative_cashflow(filename=str(out_file))
        assert out_file.exists()
        assert out_file.stat().st_size > 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))