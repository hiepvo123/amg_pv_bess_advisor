import numpy as np
import pandas as pd
import numpy_financial as npf
import matplotlib.pyplot as plt
import json
import os


class FinancialModel:
    MACRS_TABLES = {
        3: [0.3333, 0.4445, 0.1481, 0.0741],
        5: [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576],
        7: [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
        10: [0.1000, 0.1800, 0.1440, 0.1152, 0.0922, 0.0737,
             0.0655, 0.0655, 0.0656, 0.0655, 0.0328],
        15: [0.0500, 0.0950, 0.0855, 0.0770, 0.0693, 0.0623, 0.0590,
             0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590,
             0.0591, 0.0295],
        20: [0.0375, 0.0722, 0.0668, 0.0618, 0.0571, 0.0529, 0.0489,
             0.0452, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446,
             0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0223],
    }

    def __init__(
        self,
        pv_capex,

        pv_opex,
        bess_opex,

        inverter_capex=0,
        other_capex=0,

        insurance_cost = 0,

        property_tax=0,

        land_lease_cost=0,

        variable_opex_rate=0,
        
        discount_rate = 0,
        
        project_life = 20,

        pv_result=None,
        bess_result=None,

        bess_capex=0,

        battery_replacement_cost=0,
        battery_replacement_year=10,
        battery_degradation_rate=0.02,

        inverter_replacement_cost=0,
        inverter_replacement_year=12,

        price_growth_rate=0.0,
        opex_growth_rate=0.025,

        # SAM-style revenue and tax incentives.  Defaults preserve the
        # original energy-only merchant/PPA revenue calculation.
        capacity_payment=0,
        capacity_payment_growth_rate=0.0,
        production_incentive_rate=0,
        production_incentive_years=0,
        production_incentive_escalation_rate=0.0,
        investment_tax_credit_rate=0.0,
        itc_eligible_fraction=1.0,
        itc_basis_reduction_fraction=0.5,
        itc_start_year=1,

        pv_degradation_rate=0.005,

        salvage_value=0,

        loan_fraction=0.70,
        loan_interest_rate=0.08,
        loan_term=20,

        tax_rate=0.0825,

        inflation_rate=0.025,

        depreciation_years=20,
        depreciation_method="SL",

        annual_revenue=None,
        
        electricity_price=None,

        construction_period_years=0,
        idc_rate=None,

        min_dscr_threshold=1.20,

    ):

        # -----------------------
        # Capital Cost
        # -----------------------
        self.pv_capex = pv_capex or 0
        self.bess_capex = bess_capex or 0
        self.inverter_capex = inverter_capex or 0
        self.other_capex = other_capex or 0

        self.capex = (
            self.pv_capex
            + self.bess_capex
            + self.inverter_capex
            + self.other_capex
        )

        # -----------------------
        # OPEX
        # -----------------------
        self.pv_opex = pv_opex
        self.bess_opex = bess_opex

        self.pv_result = pv_result
        self.bess_result = bess_result
        

        # -----------------------
        # Project
        # -----------------------
        self.life = project_life
        self.discount_rate = discount_rate
        self.nominal_discount_rate = discount_rate
        self.real_discount_rate = (
            (1 + discount_rate)
            /
            (1 + inflation_rate)
        ) - 1

        self.annual_revenue = annual_revenue

        self.price_growth_rate = price_growth_rate
        self.opex_growth_rate = opex_growth_rate

        # Revenue can comprise energy sales, a fixed capacity payment, and
        # a time-limited production-based incentive (PBI), as in SAM.
        self.capacity_payment = capacity_payment
        self.capacity_payment_growth_rate = capacity_payment_growth_rate
        self.production_incentive_rate = production_incentive_rate
        self.production_incentive_years = production_incentive_years
        self.production_incentive_escalation_rate = (
            production_incentive_escalation_rate
        )

        # The investment tax credit is non-refundable: it offsets tax due and
        # any unused credit carries forward.  Its depreciation-basis reduction
        # follows SAM's usual 50%-of-credit convention by default.
        self.investment_tax_credit_rate = investment_tax_credit_rate
        self.itc_eligible_fraction = itc_eligible_fraction
        self.itc_basis_reduction_fraction = itc_basis_reduction_fraction
        self.itc_start_year = itc_start_year

        self.inflation_rate = inflation_rate

        self.pv_degradation_rate = pv_degradation_rate
        self.battery_degradation_rate = battery_degradation_rate

        # -----------------------
        # Replacement
        # -----------------------
        self.battery_replacement_year = self._as_year_list(battery_replacement_year)
        self.battery_replacement_cost = self._as_cost_list(
            battery_replacement_cost, self.battery_replacement_year
        )

        self.inverter_replacement_year = self._as_year_list(inverter_replacement_year)
        self.inverter_replacement_cost = self._as_cost_list(
            inverter_replacement_cost, self.inverter_replacement_year
        )

        self.salvage_value = salvage_value

        # -----------------------
        # Financing
        # -----------------------
        self.loan_fraction = loan_fraction
        self.loan_interest_rate = loan_interest_rate
        self.loan_term = loan_term

        self.tax_rate = tax_rate

        self.min_dscr_threshold = min_dscr_threshold

        # -----------------------
        # Construction period
        # -----------------------
        self.construction_period_years = construction_period_years
        self.idc_rate = idc_rate if idc_rate is not None else loan_interest_rate

        # -----------------------
        # Depreciation
        # -----------------------
        self.depreciation_method = depreciation_method
        self.depreciation_years = depreciation_years
        
      
        self.electricity_price = electricity_price
        self.replacement_depreciation = {}
        
        self.insurance_cost = insurance_cost

        self.property_tax = property_tax

        self.land_lease_cost = land_lease_cost

        self.variable_opex_rate = variable_opex_rate
        
        # -----------------------
        # Build schedules
        # -----------------------
        self.initialize_energy_inputs()
        self.energy_schedule = self.build_energy_schedule()
        self.idc = self._compute_idc()
        self.investment_tax_credit = self._compute_investment_tax_credit()
        self.validate_inputs()
        self.loan_schedule = self.build_loan_schedule()
        self.capex_schedule = self.build_capex_schedule()
        self.revenue_schedule = self.build_revenue_schedule()
        self.opex_schedule = self.build_opex_schedule()
        self.replacement_schedule = self.build_replacement_schedule()
        self.depreciation_schedule = self.build_depreciation_schedule()

    # -----------------------
    # Input normalization helpers
    # -----------------------

    @staticmethod
    def _as_year_list(years):
        """
        Normalize a replacement-year input into a list of ints, so
        callers can pass either a single year (backward compatible) or
        a list of years for multiple replacement events. A year <= 0
        means "no replacement" and is dropped.
        """
        if years is None:
            return []

        if isinstance(years, (list, tuple, set, np.ndarray, pd.Series)):
            year_list = [int(y) for y in years]
        else:
            year_list = [int(years)]

        return [y for y in year_list if y > 0]

    @staticmethod
    def _as_cost_list(costs, year_list):
        if not year_list:
            return []

        if isinstance(costs, (list, tuple, set, np.ndarray, pd.Series)):
            cost_list = [float(c) for c in costs]

            if len(cost_list) != len(year_list):
                raise ValueError(
                    "Replacement cost list must be the same length as "
                    "the replacement year list "
                    f"({len(cost_list)} costs vs {len(year_list)} years)."
                )

            return cost_list

        return [float(costs)] * len(year_list)

    def _annual_revenue_series(self):
        if isinstance(self.annual_revenue, (list, tuple, np.ndarray, pd.Series)):
            values = [float(v) for v in self.annual_revenue]

            if len(values) != self.life:
                raise ValueError(
                    f"annual_revenue list must have exactly {self.life} "
                    f"entries (one per project year), got {len(values)}."
                )

            return values

        base = float(self.annual_revenue)

        return [
            base * (1 + self.price_growth_rate) ** (y - 1)
            for y in range(1, self.life + 1)
        ]

    def _compute_idc(self):

        if not self.construction_period_years or self.construction_period_years <= 0:
            return 0.0

        debt_before_idc = self.capex * self.loan_fraction
        annual_draw = debt_before_idc / self.construction_period_years

        balance = 0.0
        idc = 0.0

        for _ in range(int(self.construction_period_years)):
            balance += annual_draw
            interest = balance * self.idc_rate
            idc += interest
            balance += interest  # capitalized, compounds into next year's balance

        return idc

    def _compute_investment_tax_credit(self):
        """Return the eligible, non-refundable investment tax credit."""
        return (
            self.capex
            * self.itc_eligible_fraction
            * self.investment_tax_credit_rate
        )

    def get_depreciation(self, year):

        row = self.depreciation_schedule.loc[
            self.depreciation_schedule["Year"] == year
        ]

        return row["Total Depreciation (VND)"].iloc[0]

    def get_interest_payment(self, year):

        if year in self.loan_schedule:
            return self.loan_schedule[year]["interest"]

        return 0
    def get_principal_payment(self, year):

        if year in self.loan_schedule:
            return self.loan_schedule[year]["principal"]

        return 0
    
    def get_exported_energy_for_year(self, year):
        if self.pv_energy is None:
            return 0

        exported = self.pv_energy

        exported *= (1 - self.pv_degradation_rate) ** (year - 1)

        return exported
    
    
    def get_revenue_for_year(self, year):

        return self.revenue_schedule.loc[
            self.revenue_schedule["Year"] == year,
            "Revenue (VND)"
        ].iloc[0]

    def get_opex_for_year(self, year):

        return self.opex_schedule.loc[
            self.opex_schedule["Year"] == year,
            "Total O&M (VND)"
        ].iloc[0]

    def get_pv_energy_for_year(self, year):
        """
        PV energy (kWh) for a given year, after degradation.
        """

        return self.energy_schedule.loc[
            self.energy_schedule["Year"] == year,
            "PV Energy (kWh)"
        ].iloc[0]

    def get_total_energy_for_year(self, year):
        return self.energy_schedule.loc[
            self.energy_schedule["Year"] == year,
            "Total Energy (kWh)"
        ].iloc[0]
        
        
    #SCHEDULE

    def build_capex_schedule(self):

        rows = []
        debt = (self.capex * self.loan_fraction) + self.idc
        equity = self.capex - (self.capex * self.loan_fraction)

        for year in range(self.life + 1):

            pv_cost = 0
            bess_cost = 0
            inverter_cost = 0
            other_cost = 0

            debt_draw = 0
            equity_draw = 0
            idc_amount = 0

            # ----------------------------------
            # Initial investment
            # ----------------------------------

            if year == 0:

                pv_cost = self.pv_capex

                bess_cost = self.bess_capex

                inverter_cost = self.inverter_capex

                other_cost = self.other_capex

                debt_draw = debt

                equity_draw = equity

                idc_amount = self.idc

            # ----------------------------------
            # Battery replacement (one or more events)
            # ----------------------------------

            battery_replacement = self._replacement_cost_for_year(
                year, self.battery_replacement_year, self.battery_replacement_cost
            )

            # ----------------------------------
            # Inverter replacement (one or more events)
            # ----------------------------------

            inverter_replacement = self._replacement_cost_for_year(
                year, self.inverter_replacement_year, self.inverter_replacement_cost
            )

            total_capex = (

                pv_cost

                + bess_cost

                + inverter_cost

                + other_cost

                + battery_replacement

                + inverter_replacement

            )

            rows.append({

                "Year": year,

                "PV CAPEX (VND)": pv_cost,

                "BESS CAPEX (VND)": bess_cost,

                "Inverter CAPEX (VND)": inverter_cost,

                "Other CAPEX (VND)": other_cost,

                "Battery Replacement (VND)": battery_replacement,

                "Inverter Replacement (VND)": inverter_replacement,

                "Total CAPEX (VND)": total_capex,

                "IDC Capitalized (VND)": idc_amount,

                # Total project cost is the use of funds.  Keeping IDC out of
                # the equipment CAPEX columns avoids depreciating financing
                # cost while still making sources and uses reconcile.
                "Total Project Cost (VND)": total_capex + idc_amount,

                "Debt Draw (VND)": debt_draw,

                "Equity Draw (VND)": equity_draw

            })

        return pd.DataFrame(rows)

    @staticmethod
    def _replacement_cost_for_year(year, year_list, cost_list):
        """
        Sum replacement cost(s) landing in `year`. year_list/cost_list are
        parallel lists (see _as_year_list / _as_cost_list), so this
        naturally supports multiple replacement events -- including two
        events falling in the same year, which get summed.
        """
        return sum(
            cost
            for evt_year, cost in zip(year_list, cost_list)
            if evt_year == year
        )

    def build_energy_schedule(self):
        """
        Annual PV/BESS energy schedule.

        This schedule is the source for:
            - Revenue Schedule
            - LCOE
            - LCOS
            - Cash Flow
        """

        rows = []

        for year in range(1, self.life + 1):

            # -------------------------
            # PV degradation
            # -------------------------

            pv_energy = (
                self.pv_energy
                *
                (
                    (1 - self.pv_degradation_rate)
                    ** (year - 1)
                )
            )

            # -------------------------
            # Battery degradation
            # -------------------------

            # A replacement restores the battery's first-year delivery
            # capability.  This is materially different from simply adding a
            # replacement CAPEX item while leaving energy on the old declining
            # degradation curve.
            latest_replacement = max(
                [1] + [
                    replacement_year
                    for replacement_year, replacement_cost in zip(
                        self.battery_replacement_year,
                        self.battery_replacement_cost,
                    )
                    if replacement_year <= year and replacement_cost > 0
                ]
            )
            bess_age = year - latest_replacement
            bess_energy = self.bess_energy * (
                (1 - self.battery_degradation_rate) ** bess_age
            )

            total_energy = (
                pv_energy
                + bess_energy
            )

            rows.append({

                "Year": year,

                "PV Energy (kWh)": pv_energy,

                "BESS Energy (kWh)": bess_energy,

                "Total Energy (kWh)": total_energy

            })

        return pd.DataFrame(rows)
    
    def build_revenue_schedule(self):

        rows = []

        override = (
            self._annual_revenue_series()
            if self.annual_revenue is not None
            else None
        )

        for year in range(1, self.life + 1):

            row = self.energy_schedule.loc[
                self.energy_schedule["Year"] == year
            ].iloc[0]

            pv_energy = row["PV Energy (kWh)"]
            bess_energy = row["BESS Energy (kWh)"]
            energy = row["Total Energy (kWh)"]

            if override is not None:
                # An explicit annual_revenue series is a total revenue
                # override, retaining the legacy contract.
                revenue = override[year - 1]
                price = (revenue / energy) if energy else 0
                energy_sales_revenue = revenue
                capacity_revenue = 0
                production_incentive = 0
            else:
                price = self.electricity_price * (
                    (1 + self.price_growth_rate) ** (year - 1)
                )
                energy_sales_revenue = energy * price
                capacity_revenue = self.capacity_payment * (
                    (1 + self.capacity_payment_growth_rate) ** (year - 1)
                )
                production_incentive = 0
                if year <= self.production_incentive_years:
                    production_incentive = energy * self.production_incentive_rate * (
                        (1 + self.production_incentive_escalation_rate) ** (year - 1)
                    )
                revenue = (
                    energy_sales_revenue
                    + capacity_revenue
                    + production_incentive
                )

            rows.append({

                "Year": year,

                "PV Energy (kWh)": pv_energy,

                "BESS Energy (kWh)": bess_energy,

                "Total Energy (kWh)": energy,

                "Electricity Price (VND/kWh)": price,

                "Energy Sales Revenue (VND)": energy_sales_revenue,

                "Capacity Revenue (VND)": capacity_revenue,

                "Production Incentive (VND)": production_incentive,

                "Revenue (VND)": revenue

            })

        return pd.DataFrame(rows)
    
    def build_opex_schedule(self):
        rows = []

        for year in range(1, self.life + 1):

            growth = (
                1 + self.opex_growth_rate
            ) ** (year - 1)

            fixed_pv = self.pv_opex * growth

            fixed_bess = self.bess_opex * growth

            insurance = self.insurance_cost * growth

            property_tax = self.property_tax * growth

            land_lease = self.land_lease_cost * growth

            # Variable O&M scales with total energy throughput (PV + BESS
            # discharge), not PV alone -- see get_total_energy_for_year().
            variable = (
                self.variable_opex_rate
                * self.get_total_energy_for_year(year)
            )

            total = (

                fixed_pv

                + fixed_bess

                + insurance

                + property_tax

                + land_lease

                + variable

            )

            rows.append({

                "Year": year,

                "PV O&M (VND)": fixed_pv,

                "BESS O&M (VND)": fixed_bess,

                "Insurance (VND)": insurance,

                "Property Tax (VND)": property_tax,

                "Land Lease (VND)": land_lease,

                "Variable O&M (VND)": variable,

                "Total O&M (VND)": total

            })

        return pd.DataFrame(rows)
    
    def build_depreciation_schedule(self):
        if self.depreciation_method.upper() == "SL":

            base_rate = 1 / self.depreciation_years

            base_rates = [base_rate] * self.depreciation_years

        elif self.depreciation_method.upper() == "MACRS":

            if self.depreciation_years not in self.MACRS_TABLES:
                raise ValueError(
                    f"No standard MACRS table for depreciation_years="
                    f"{self.depreciation_years}. Supported MACRS class "
                    f"lives: {sorted(self.MACRS_TABLES)}."
                )

            base_rates = self.MACRS_TABLES[self.depreciation_years]

        else:

            raise ValueError(
                "Unknown depreciation method."
            )

        gross_initial_asset = (
            self.pv_capex
            + self.bess_capex
            + self.inverter_capex
            + self.other_capex
        )

        # Tax credits reduce depreciable basis but are not themselves an
        # operating expense.  With the default 50% reduction this follows the
        # convention used for the U.S. federal ITC in SAM.
        initial_asset = max(
            gross_initial_asset
            - self.investment_tax_credit * self.itc_basis_reduction_fraction,
            0,
        )

        def share(component_capex):
            return (
                (component_capex / gross_initial_asset)
                if gross_initial_asset
                else 0
            )

        pv_share = share(self.pv_capex)
        bess_share = share(self.bess_capex)
        inverter_share = share(self.inverter_capex)
        other_share = share(self.other_capex)

        rows = []

        accumulated = 0

        for year in range(1, self.life + 1):

            if year <= len(base_rates):

                base_dep = initial_asset * base_rates[year - 1]

                dep_rate = base_rates[year - 1] * 100

            else:

                base_dep = 0

                dep_rate = 0

            # --------------------------
            # Battery replacement depreciation
            # --------------------------

            battery_dep = 0

            for _, row in self.replacement_schedule.iterrows():

                # ``iterrows`` may upcast an otherwise integer Year column
                # to numpy.float64 when the row also contains float/NaN
                # fields.  MACRS rates are list-indexed, so normalize it.
                install_year = int(row["Year"])

                replacement_cost = row["Battery Replacement (VND)"]

                if replacement_cost == 0:
                    continue

                age = int(year - install_year)

                if 0 <= age < len(base_rates):
                    battery_dep += replacement_cost * base_rates[age]

            # --------------------------
            # Inverter replacement depreciation
            # --------------------------

            inverter_replacement_dep = 0

            for _, row in self.replacement_schedule.iterrows():

                install_year = int(row["Year"])

                replacement_cost = row["Inverter Replacement (VND)"]

                if replacement_cost == 0:
                    continue

                age = int(year - install_year)

                if 0 <= age < len(base_rates):
                    inverter_replacement_dep += replacement_cost * base_rates[age]

            total_dep = (
                base_dep
                + battery_dep
                + inverter_replacement_dep
            )

            accumulated += total_dep

            asset_value = initial_asset + sum(
                replacement["Battery Replacement (VND)"]
                + replacement["Inverter Replacement (VND)"]
                for _, replacement in self.replacement_schedule.loc[
                    self.replacement_schedule["Year"] <= year
                ].iterrows()
            )

            book_value = max(asset_value - accumulated, 0)

            rows.append({

                "Year": year,

                "Depreciation Rate (%)": dep_rate,

                "Asset Value (VND)": asset_value,

                "Base Depreciation (VND)": base_dep,

                "PV Depreciation (VND)": base_dep * pv_share,

                "BESS Depreciation (VND)": base_dep * bess_share,

                "Inverter Depreciation (VND)": base_dep * inverter_share,

                "Other Depreciation (VND)": base_dep * other_share,

                "Battery Replacement Depreciation (VND)": battery_dep,

                "Inverter Replacement Depreciation (VND)": inverter_replacement_dep,

                "Total Depreciation (VND)": total_dep,

                "Accumulated Depreciation (VND)": accumulated,

                "Book Value (VND)": book_value

            })

        return pd.DataFrame(rows)
    
    def build_replacement_schedule(self):
        rows = []

        for year in range(1, self.life + 1):

            battery_cost = self._replacement_cost_for_year(
                year, self.battery_replacement_year, self.battery_replacement_cost
            )

            inverter_cost = self._replacement_cost_for_year(
                year, self.inverter_replacement_year, self.inverter_replacement_cost
            )

            total = (

                battery_cost

                + inverter_cost

            )

            rows.append({

                "Year": year,

                "Battery Replacement (VND)": battery_cost,

                "Inverter Replacement (VND)": inverter_cost,

                "Total Replacement (VND)": total,
                
                "Battery Depreciation Start": (
                    year if battery_cost > 0 else None
                ),

                "Inverter Depreciation Start": (
                    year if inverter_cost > 0 else None
                )

            })

        return pd.DataFrame(rows)
    
    def build_loan_schedule(self):
        if self.loan_fraction == 0:
            return {}
        loan_amount = (self.capex * self.loan_fraction) + self.idc

        annual_payment = abs(
            npf.pmt(
                self.loan_interest_rate,
                self.loan_term,
                loan_amount
            )
        )

        balance = loan_amount

        schedule = {}

        for year in range(1, self.loan_term + 1):

            interest = balance * self.loan_interest_rate

            principal = annual_payment - interest

            balance -= principal

            schedule[year] = {

                "payment": annual_payment,

                "interest": interest,

                "principal": principal,

                "balance": max(balance, 0)

            }

        return schedule
    
    #HELPER FUNCTION
    
    def get_replacement_depreciation(self, year):
        depreciation = 0

        for start_year, annual_dep, years_left in self.replacement_depreciation.values():

            if start_year <= year < start_year + years_left:
                depreciation += annual_dep

        return depreciation
    
    @staticmethod
    def _infer_interval_hours(df, datetime_col="datetime", default_hours=0.5):
        if datetime_col not in df.columns or len(df) < 2:
            return default_hours

        ts = pd.to_datetime(df[datetime_col]).sort_values()
        diffs = ts.diff().dropna().dt.total_seconds() / 3600.0

        if diffs.empty:
            return default_hours

        return diffs.median()

    def initialize_energy_inputs(self):
        # --------------------------
        # PV
        # --------------------------
        if self.pv_result is not None:

            if "pv_power_calc" not in self.pv_result.columns:
                raise ValueError(
                    "pv_result must contain column 'pv_power_calc'"
                )

            interval_hours = self._infer_interval_hours(self.pv_result)

            dataset_energy_mwh = (
                self.pv_result["pv_power_calc"].sum()
                * interval_hours
            )

            if "date" in self.pv_result.columns:
                days = self.pv_result["date"].nunique()
            else:
                days = (
                    pd.to_datetime(self.pv_result["datetime"])
                    .dt.date.nunique()
                )

            annual_factor = 365 / days

            self.pv_energy = (
                dataset_energy_mwh
                * annual_factor
                * 1000
            )

        else:
            self.pv_energy = 0

        # --------------------------
        # BESS
        # --------------------------
        if self.bess_result is not None:

            if "energy_out_kwh" not in self.bess_result.columns:
                raise ValueError(
                    "bess_result must contain 'energy_out_kwh'"
                )

            simulated_bess_energy = (
                self.bess_result["energy_out_kwh"].sum()
            )

            if "date" in self.bess_result.columns:
                days = self.bess_result["date"].nunique()
            elif "datetime" in self.bess_result.columns:
                days = (
                    pd.to_datetime(self.bess_result["datetime"])
                    .dt.date.nunique()
                )
            else:
                days = len(self.bess_result) / 48

            annual_factor = 365 / days
            self.bess_energy = simulated_bess_energy * annual_factor

        else:
            self.bess_energy = 0
            
    def present_value_total_pv_cost(self):

        total = (
        self.pv_capex
    )

        for year in range(1, self.life + 1):

            discount = (1 + self.real_discount_rate) ** year

            opex_growth = (1 + self.opex_growth_rate) ** (year - 1)

            total += (
                self.pv_opex * opex_growth
                /
                discount
            )

            inverter_replacement = self._replacement_cost_for_year(
                year, self.inverter_replacement_year, self.inverter_replacement_cost
            )

            if inverter_replacement:
                total += (
                    inverter_replacement
                    / discount
                )

        # Salvage value reduces lifecycle cost
        discount = (1 + self.real_discount_rate) ** self.life

        total -= (
            self.salvage_value * (1 - self.tax_rate)
        ) / discount

        return total

    def present_value_total_pv_energy(self):

        total = 0

        for year in range(1, self.life + 1):

            energy = (
                self.pv_energy
                *
                ((1 - self.pv_degradation_rate) ** (year - 1))
            )

            total += (
                energy
                /
                ((1 + self.real_discount_rate) ** year)
            )

        return total
    
    def present_value_total_bess_cost(self):

        total = self.bess_capex

        for year in range(1, self.life + 1):

            discount = (1 + self.real_discount_rate) ** year

            opex_growth = (1 + self.opex_growth_rate) ** (year - 1)

            total += (
                self.bess_opex * opex_growth
                /
                discount
            )

            battery_replacement = self._replacement_cost_for_year(
                year, self.battery_replacement_year, self.battery_replacement_cost
            )

            if battery_replacement:

                total += (
                    battery_replacement
                    /
                    discount
                )

        discount = (1 + self.real_discount_rate) ** self.life

        total -= (
            self.salvage_value * (1 - self.tax_rate)
        ) / discount

        return total

    def present_value_total_opex(self):
        total = 0

        for year in range(1, self.life + 1):

            opex = self.get_opex_for_year(year)

            discount = (1 + self.discount_rate) ** year

            total += opex / discount

        return total

    def validate_inputs(self):

        assert self.capex > 0, "Total CAPEX must be > 0."

        assert self.life > 0, "project_life must be > 0."

        assert self.discount_rate >= 0, "discount_rate cannot be negative."

        assert self.loan_fraction >= 0, "loan_fraction cannot be negative."

        assert self.loan_fraction <= 1, "loan_fraction cannot exceed 1."

        assert self.tax_rate >= 0, "tax_rate cannot be negative."

        assert self.tax_rate <= 1, "tax_rate cannot exceed 1."

        assert 0 <= self.investment_tax_credit_rate <= 1, (
            "investment_tax_credit_rate must be between 0 and 1."
        )

        assert 0 <= self.itc_eligible_fraction <= 1, (
            "itc_eligible_fraction must be between 0 and 1."
        )

        assert 0 <= self.itc_basis_reduction_fraction <= 1, (
            "itc_basis_reduction_fraction must be between 0 and 1."
        )

        assert self.production_incentive_years >= 0, (
            "production_incentive_years cannot be negative."
        )

        assert 1 <= self.itc_start_year <= self.life, (
            "itc_start_year must fall within the operating project life."
        )

        assert self.construction_period_years >= 0, (
            "construction_period_years cannot be negative."
        )

        if self.loan_fraction > 0:
            assert self.loan_term > 0, (
                "loan_term must be > 0 when loan_fraction > 0."
            )

        assert self.electricity_price is not None or self.annual_revenue is not None, (
            "Either electricity_price or annual_revenue must be provided "
            "-- revenue cannot be computed with both unset."
        )

        if self.annual_revenue is None:
            assert (self.pv_energy or 0) > 0 or (self.bess_energy or 0) > 0, (
                "electricity_price was provided but there is no PV or BESS "
                "energy (pv_result/bess_result) to apply it to."
            )
        
        
    def present_value_discharged_bess_energy(self):

        total = 0

        for year in range(1, self.life + 1):

            energy = self.energy_schedule.loc[
                self.energy_schedule["Year"] == year,
                "BESS Energy (kWh)",
            ].iloc[0]

            total += (
                energy
                /
                ((1 + self.real_discount_rate) ** year)
            )

        return total
    

    def get_replacement_cost(self, year):

        rows = self.replacement_schedule.loc[
            self.replacement_schedule["Year"] == year
        ]

        return rows["Total Replacement (VND)"].iloc[0]


# Cash Flow
    def calculate_cash_flow(self):
        """Build a SAM-style, after-tax annual project and equity cash flow."""
        rows = []
        tax_loss_balance = 0.0
        itc_credit_balance = 0.0

        debt = self.capex_schedule.loc[
            self.capex_schedule["Year"] == 0, "Debt Draw (VND)"
        ].iloc[0]
        equity = self.capex_schedule.loc[
            self.capex_schedule["Year"] == 0, "Equity Draw (VND)"
        ].iloc[0]
        cumulative = -equity

        rows.append({
            "Year": 0, "Energy (kWh)": 0, "Revenue (VND)": 0,
            "OPEX (VND)": 0, "EBITDA (VND)": 0, "Depreciation (VND)": 0,
            "EBIT (VND)": 0, "Interest (VND)": 0, "Principal (VND)": 0,
            "Loan Balance (VND)": debt, "Taxable Income (VND)": 0,
            "Tax Loss Used (VND)": 0, "Tax Loss Carryforward (VND)": 0,
            "ITC Generated (VND)": 0, "ITC Applied (VND)": 0,
            "ITC Carryforward (VND)": 0, "Income Tax (VND)": 0,
            "Net Income (VND)": 0, "Replacement (VND)": 0,
            "Salvage (VND)": 0, "Terminal Gain/Loss (VND)": 0,
            "Operating Cash Flow (VND)": 0,
            "Project Cash Flow (VND)": -(self.capex + self.idc),
            "Equity Cash Flow (VND)": -equity, "Discount Factor": 1,
            "Discounted Cash Flow (VND)": -equity,
            "Cumulative Cash Flow (VND)": cumulative, "CFADS (VND)": 0,
            "Debt Service (VND)": 0, "DSCR": None,
        })

        for year in range(1, self.life + 1):
            energy = self.get_total_energy_for_year(year)
            revenue = self.get_revenue_for_year(year)
            opex = self.get_opex_for_year(year)
            ebitda = revenue - opex
            depreciation = self.get_depreciation(year)
            ebit = ebitda - depreciation

            loan = self.loan_schedule.get(
                year, {"interest": 0, "principal": 0, "balance": 0}
            )
            interest = loan["interest"]
            principal = loan["principal"]
            loan_balance = loan["balance"]
            replacement = self.get_replacement_cost(year)

            book_value = self.depreciation_schedule.loc[
                self.depreciation_schedule["Year"] == year, "Book Value (VND)"
            ].iloc[0]
            terminal_gain_or_loss = (
                self.salvage_value - book_value if year == self.life else 0
            )
            salvage = self.salvage_value if year == self.life else 0

            taxable_income = ebit - interest + terminal_gain_or_loss
            tax_loss_used = 0.0
            if taxable_income > 0 and tax_loss_balance > 0:
                tax_loss_used = min(taxable_income, tax_loss_balance)
                taxable_income -= tax_loss_used
                tax_loss_balance -= tax_loss_used
            elif taxable_income < 0:
                tax_loss_balance += -taxable_income
                taxable_income = 0.0

            pre_credit_tax = taxable_income * self.tax_rate
            itc_generated = (
                self.investment_tax_credit if year == self.itc_start_year else 0
            )
            itc_credit_balance += itc_generated
            itc_applied = min(pre_credit_tax, itc_credit_balance)
            itc_credit_balance -= itc_applied
            income_tax = pre_credit_tax - itc_applied

            net_income = ebit - interest + terminal_gain_or_loss - income_tax
            operating_cf = ebitda - income_tax
            project_cf = operating_cf - replacement + salvage
            equity_cf = project_cf - interest - principal

            discount = 1 / (1 + self.discount_rate) ** year
            discounted_cf = equity_cf * discount
            cumulative += discounted_cf
            cfads = ebitda - income_tax - replacement
            debt_service = interest + principal
            dscr = cfads / debt_service if debt_service > 0 else None

            rows.append({
                "Year": year, "Energy (kWh)": energy, "Revenue (VND)": revenue,
                "OPEX (VND)": opex, "EBITDA (VND)": ebitda,
                "Depreciation (VND)": depreciation, "EBIT (VND)": ebit,
                "Interest (VND)": interest, "Principal (VND)": principal,
                "Loan Balance (VND)": loan_balance,
                "Taxable Income (VND)": taxable_income,
                "Tax Loss Used (VND)": tax_loss_used,
                "Tax Loss Carryforward (VND)": tax_loss_balance,
                "ITC Generated (VND)": itc_generated,
                "ITC Applied (VND)": itc_applied,
                "ITC Carryforward (VND)": itc_credit_balance,
                "Income Tax (VND)": income_tax, "Net Income (VND)": net_income,
                "Replacement (VND)": replacement, "Salvage (VND)": salvage,
                "Terminal Gain/Loss (VND)": terminal_gain_or_loss,
                "Operating Cash Flow (VND)": operating_cf,
                "Project Cash Flow (VND)": project_cf,
                "Equity Cash Flow (VND)": equity_cf,
                "Discount Factor": discount,
                "Discounted Cash Flow (VND)": discounted_cf,
                "Cumulative Cash Flow (VND)": cumulative, "CFADS (VND)": cfads,
                "Debt Service (VND)": debt_service, "DSCR": dscr,
            })

        return pd.DataFrame(rows)
    
    #NPV
    def calculate_npv(self):
        "Net Present Value"
        cashflow = self.calculate_cash_flow()

        return cashflow[
            "Discounted Cash Flow (VND)"
        ].sum()

    def calculate_project_npv(self):
        """Unlevered after-tax NPV, separate from the equity-holder NPV."""
        cashflow = self.calculate_cash_flow()
        return sum(
            row["Project Cash Flow (VND)"] / (1 + self.discount_rate) ** row["Year"]
            for _, row in cashflow.iterrows()
        )


    #IRR
    def calculate_irr(self):
        """
        Internal Rate of Return.
        """
        cashflow = self.calculate_cash_flow()

        return npf.irr(

            cashflow["Equity Cash Flow (VND)"]

        )


    #Paypack Period
    def calculate_payback(self):
        """
        Discounted Payback Period.

        Reuses the "Discounted Cash Flow" / "Cumulative Cash Flow"
        columns already produced by calculate_cash_flow() instead of
        recomputing the discounting a second time with the same rate.
        """

        cashflow = self.calculate_cash_flow()

        previous_cumulative = 0.0

        for _, row in cashflow.iterrows():

            year = row["Year"]

            discounted_cf = row["Discounted Cash Flow (VND)"]

            cumulative = row["Cumulative Cash Flow (VND)"]

            if cumulative >= 0:

                if year == 0:
                    return 0

                return (
                    (year - 1)
                    + abs(previous_cumulative) / discounted_cf
                )

            previous_cumulative = cumulative

        return None


    #LCOE
    def calculate_lcoe(self):
        """
        Levelized Cost of Energy.
        Unit: VND/kWh
        """
        if self.pv_energy is None:
            return None

        pv_cost = self.present_value_total_pv_cost()

        pv_energy = self.present_value_total_pv_energy()

        if pv_energy <= 0:
            return None

        return pv_cost / pv_energy

    #LCOS
    def calculate_lcos(self):
        """
        Levelized Cost of Storage.
        Unit: VND/kWh
        """
        if self.bess_energy is None:
            return None

        cost = self.present_value_total_bess_cost()

        energy = self.present_value_discharged_bess_energy()

        if energy <= 0:
            return None

        return cost / energy


    #DSCR
    def calculate_dscr_summary(self):
        """
        Debt Service Coverage Ratio summary over the years debt service is
        actually owed (DSCR is undefined, and excluded, in years with no
        debt service -- e.g. an unlevered project, or after the loan is
        repaid while project_life continues).

        Returns a dict with:
            - "Min DSCR": lowest annual DSCR over the loan term
            - "Min DSCR Year": the year it occurs in
            - "Average DSCR": mean annual DSCR over the loan term
            - "Meets Min DSCR Threshold": whether Min DSCR >= min_dscr_threshold
            - "DSCR by Year": {year: dscr} for every year with debt service
        All values are None if there is no debt (loan_fraction == 0).
        """

        cashflow = self.calculate_cash_flow()

        dscr_rows = cashflow.loc[
            cashflow["DSCR"].notna(),
            ["Year", "DSCR"]
        ]

        if dscr_rows.empty:
            return {
                "Min DSCR": None,
                "Min DSCR Year": None,
                "Average DSCR": None,
                "Meets Min DSCR Threshold": None,
                "DSCR by Year": {},
            }

        min_row = dscr_rows.loc[dscr_rows["DSCR"].idxmin()]

        return {
            "Min DSCR": min_row["DSCR"],
            "Min DSCR Year": int(min_row["Year"]),
            "Average DSCR": dscr_rows["DSCR"].mean(),
            "Meets Min DSCR Threshold": bool(
                min_row["DSCR"] >= self.min_dscr_threshold
            ),
            "DSCR by Year": dict(
                zip(dscr_rows["Year"].astype(int), dscr_rows["DSCR"])
            ),
        }


    #Summary
    def calculate_financial_metrics(self):
        """
        Financial Summary
        Similar to NREL SAM Summary page.
        """

        capex = self.capex_schedule
        revenue = self.revenue_schedule
        opex = self.opex_schedule
        lifetime_opex = opex["Total O&M (VND)"].sum()
        dscr_summary = self.calculate_dscr_summary()

        summary = {

            "PV CAPEX (VND)":
                capex["PV CAPEX (VND)"].sum(),

            "BESS CAPEX (VND)":
                capex["BESS CAPEX (VND)"].sum(),

            "Inverter CAPEX (VND)":
                capex["Inverter CAPEX (VND)"].sum(),

            "Other CAPEX (VND)":
                capex["Other CAPEX (VND)"].sum(),

            "Battery Replacement CAPEX (VND)":
                capex["Battery Replacement (VND)"].sum(),

            "Inverter Replacement CAPEX (VND)":
                capex["Inverter Replacement (VND)"].sum(),

            "Total CAPEX (VND)": self.capex,

            "Total Project Cost (VND)": self.capex + self.idc,

            "IDC Capitalized (VND)": self.idc,

            "Investment Tax Credit (VND)": self.investment_tax_credit,

            "Debt Amount (VND)": (self.capex * self.loan_fraction) + self.idc,

            "Equity Investment (VND)": self.capex * (1 - self.loan_fraction),

            "Debt Fraction (%)": self.loan_fraction * 100,

            # ----------------------------
            # Revenue
            # ----------------------------
            "Year 1 Revenue (VND)":
                revenue.iloc[0]["Revenue (VND)"],

            "Lifetime Revenue (VND)":
                revenue["Revenue (VND)"].sum(),

            # ----------------------------
            # OPEX
            # ----------------------------
            "Year 1 OPEX (VND)": opex.iloc[0]["Total O&M (VND)"],

            "Lifetime OPEX (VND)": lifetime_opex,
            "Lifetime OPEX NPV (VND)": self.present_value_total_opex(),

            # ----------------------------
            # Energy
            # ----------------------------
            "Year 1 PV Energy (kWh)":
                self.energy_schedule.iloc[0]["PV Energy (kWh)"],

            "Year 1 BESS Energy (kWh)":
                self.energy_schedule.iloc[0]["BESS Energy (kWh)"],

            "Year 1 Total Energy (kWh)":
                self.energy_schedule.iloc[0]["Total Energy (kWh)"],

            # ----------------------------
            # Financial indicators
            # ----------------------------
            "NPV (VND)":
                self.calculate_npv(),

            "Project NPV (VND)": self.calculate_project_npv(),

            "IRR (%)":
                self.calculate_irr()*100,

            "Payback (Years)":
                self.calculate_payback(),

            "LCOE (VND/kWh)":
                self.calculate_lcoe(),

            "LCOS (VND/kWh)":
                self.calculate_lcos(),

            # ----------------------------
            # DSCR
            # ----------------------------
            "Min DSCR": dscr_summary["Min DSCR"],

            "Min DSCR Year": dscr_summary["Min DSCR Year"],

            "Average DSCR": dscr_summary["Average DSCR"],

            "Meets Min DSCR Threshold": dscr_summary["Meets Min DSCR Threshold"]
        }

        return summary

    def _summary_table_rows(self):
        """
        Build (label, value, unit) rows for the SAM-style summary, shared
        by print_summary() and the "Summary" sheet in export_cashflow_excel().
        Mirrors the layout of SAM's Single Owner "Metrics" panel where an
        equivalent value exists (Total capital cost, Equity, Debt, Debt
        fraction, NPV, IRR, LCOE), plus OPEX, Payback, and LCOS as requested.
        """

        m = self.calculate_financial_metrics()

        return [
            ("SYSTEM COSTS", "", ""),
            ("PV CAPEX", m["PV CAPEX (VND)"], "VND"),
            ("BESS CAPEX", m["BESS CAPEX (VND)"], "VND"),
            ("Total capital cost (CAPEX)", m["Total CAPEX (VND)"], "VND"),
            ("Total project cost (incl. IDC)", m["Total Project Cost (VND)"], "VND"),

            ("FINANCING", "", ""),
            ("Equity", m["Equity Investment (VND)"], "VND"),
            ("Size of debt", m["Debt Amount (VND)"], "VND"),
            ("Interest during construction (IDC)", m["IDC Capitalized (VND)"], "VND"),
            ("Investment tax credit", m["Investment Tax Credit (VND)"], "VND"),

            ("OPERATING COSTS", "", ""),
            ("Year 1 OPEX", m["Year 1 OPEX (VND)"], "VND"),
            ("Lifetime OPEX (NPV)", m["Lifetime OPEX NPV (VND)"], "VND"),

            ("KEY METRICS", "", ""),
            ("NPV", m["NPV (VND)"], "VND"),
            ("Project NPV", m["Project NPV (VND)"], "VND"),
            ("IRR", m["IRR (%)"], "%"),
            ("Payback period", m["Payback (Years)"], "years"),
            ("LCOE, nominal", m["LCOE (VND/kWh)"], "VND/kWh"),
            ("LCOS, nominal", m["LCOS (VND/kWh)"], "VND/kWh"),

            ("DEBT SERVICE COVERAGE", "", ""),
            ("Min DSCR", m["Min DSCR"], "x"),
            ("Min DSCR Year", m["Min DSCR Year"], "year"),
            ("Average DSCR", m["Average DSCR"], "x"),
            ("Meets Min DSCR Threshold", m["Meets Min DSCR Threshold"], ""),
        ]

    #Print Summary
    def print_summary(self):
        """
        Print a concise, SAM-style summary of the project's key financial
        indicators: CAPEX, OPEX, NPV, IRR, Payback, LCOE, LCOS -- similar
        in spirit to the "Metrics" panel on SAM's Single Owner Inputs sheet.
        """

        m = self.calculate_financial_metrics()

        def money(x):
            if x is None:
                return "N/A"
            return f"{x:,.0f} VND"

        def per_kwh(x):
            if x is None:
                return "N/A"
            return f"{x:,.2f} VND/kWh"

        def pct(x):
            if x is None:
                return "N/A"
            return f"{x:,.2f} %"

        def years(x):
            if x is None:
                return "Not achieved within project life"
            return f"{x:,.2f} yrs"

        lines = []
        lines.append("=" * 60)
        lines.append("FINANCIAL SUMMARY".center(60))
        lines.append("=" * 60)

        lines.append("")
        lines.append("SYSTEM COSTS")
        lines.append(f"  {'PV CAPEX':<28}: {money(m['PV CAPEX (VND)'])}")
        lines.append(f"  {'BESS CAPEX':<28}: {money(m['BESS CAPEX (VND)'])}")
        lines.append(f"  {'Total CAPEX':<28}: {money(m['Total CAPEX (VND)'])}")
        lines.append(f"  {'Total project cost':<28}: {money(m['Total Project Cost (VND)'])}")

        lines.append("")
        lines.append("FINANCING")
        lines.append(
            f"  {'Equity Investment':<28}: {money(m['Equity Investment (VND)'])} "
            f"({100 - m['Debt Fraction (%)']:.1f}%)"
        )
        lines.append(
            f"  {'Debt Amount':<28}: {money(m['Debt Amount (VND)'])} "
            f"({m['Debt Fraction (%)']:.1f}%)"
        )
        if m["IDC Capitalized (VND)"]:
            lines.append(
                f"  {'  of which IDC':<28}: {money(m['IDC Capitalized (VND)'])}"
            )
        if m["Investment Tax Credit (VND)"]:
            lines.append(
                f"  {'Investment tax credit':<28}: {money(m['Investment Tax Credit (VND)'])}"
            )

        lines.append("")
        lines.append("OPERATING COSTS (OPEX)")
        lines.append(f"  {'Year 1 OPEX':<28}: {money(m['Year 1 OPEX (VND)'])}")
        lines.append(f"  {'Lifetime OPEX (NPV)':<28}: {money(m['Lifetime OPEX NPV (VND)'])}")

        lines.append("")
        lines.append("KEY METRICS")
        lines.append(f"  {'NPV':<28}: {money(m['NPV (VND)'])}")
        lines.append(f"  {'Project NPV':<28}: {money(m['Project NPV (VND)'])}")
        lines.append(f"  {'IRR':<28}: {pct(m['IRR (%)'])}")
        lines.append(f"  {'Payback Period':<28}: {years(m['Payback (Years)'])}")
        lines.append(f"  {'LCOE':<28}: {per_kwh(m['LCOE (VND/kWh)'])}")
        lines.append(f"  {'LCOS':<28}: {per_kwh(m['LCOS (VND/kWh)'])}")

        lines.append("")
        lines.append("DEBT SERVICE COVERAGE")
        if m["Min DSCR"] is None:
            lines.append(f"  {'DSCR':<28}: N/A (no debt service)")
        else:
            status = "OK" if m["Meets Min DSCR Threshold"] else "BELOW THRESHOLD"
            lines.append(
                f"  {'Min DSCR':<28}: {m['Min DSCR']:.2f}x "
                f"(Year {m['Min DSCR Year']}, threshold "
                f"{self.min_dscr_threshold:.2f}x -- {status})"
            )
            lines.append(f"  {'Average DSCR':<28}: {m['Average DSCR']:.2f}x")

        lines.append("=" * 60)

        report = "\n".join(lines)
        print(report)

        return report

    def build_financial_summary(self):
        """
        Final financial summary similar to NREL SAM.
        """

        dscr_summary = self.calculate_dscr_summary()

        summary = {

            # ------------------------
            # Capital Cost
            # ------------------------
            "PV CAPEX (VND)": self.pv_capex,
            "BESS CAPEX (VND)": self.bess_capex,
            "Inverter CAPEX (VND)": self.inverter_capex,
            "Other CAPEX (VND)": self.other_capex,
            "Total CAPEX (VND)": self.capex,
            "Total Project Cost (VND)": self.capex + self.idc,

            # ------------------------
            # OPEX
            # ------------------------
            "Year 1 PV OPEX (VND)": self.pv_opex,
            "Year 1 BESS OPEX (VND)": self.bess_opex,
            "Year 1 Total OPEX (VND)": self.get_opex_for_year(1),

            # ------------------------
            # Energy
            # ------------------------
            "Year 1 PV Energy (kWh)": self.energy_schedule.iloc[0]["PV Energy (kWh)"],
            "Year 1 BESS Energy (kWh)": self.energy_schedule.iloc[0]["BESS Energy (kWh)"],

            # ------------------------
            # Revenue
            # ------------------------
            "Year 1 Revenue (VND)": self.revenue_schedule.iloc[0]["Revenue (VND)"],

            # ------------------------
            # Financing
            # ------------------------
            "Debt (VND)": (self.capex * self.loan_fraction) + self.idc,
            "Equity (VND)": self.capex * (1 - self.loan_fraction),
            "IDC Capitalized (VND)": self.idc,
            "Investment Tax Credit (VND)": self.investment_tax_credit,

            # ------------------------
            # Financial Indicators
            # ------------------------
            "NPV (VND)": self.calculate_npv(),
            "Project NPV (VND)": self.calculate_project_npv(),
            "IRR (%)": self.calculate_irr() * 100,
            "Payback (Years)": self.calculate_payback(),
            "LCOE (VND/kWh)": self.calculate_lcoe(),
            "LCOS (VND/kWh)": self.calculate_lcos(),

            # ------------------------
            # DSCR
            # ------------------------
            "Min DSCR": dscr_summary["Min DSCR"],
            "Average DSCR": dscr_summary["Average DSCR"],
            "Meets Min DSCR Threshold": dscr_summary["Meets Min DSCR Threshold"],
        }

        return pd.Series(summary)
    
    
    #Export Result
    def export_cashflow_excel(
        self,
        filename="outputs/cashflow.xlsx"
    ):
        """
        Export cash flow table to Excel.
        """

        table = self.calculate_cash_flow()

        summary_rows = self._summary_table_rows()

        with pd.ExcelWriter(filename) as writer:

            pd.DataFrame(
                summary_rows,
                columns=["Metric", "Value", "Unit"]
            ).to_excel(

                writer,

                sheet_name="Summary",

                index=False

            )

            table.to_excel(

                writer,

                sheet_name="Cash Flow",

                index=False

            )
            self.capex_schedule.to_excel(

                writer,

                sheet_name="CAPEX",

                index=False

            )
            self.energy_schedule.to_excel(

                writer,

                sheet_name="Energy",

                index=False

            )
            self.revenue_schedule.to_excel(

                writer,

                sheet_name="Revenue",

                index=False

            )
            
            self.opex_schedule.to_excel(

                writer,

                sheet_name="OPEX",

                index=False

            )
            
            self.depreciation_schedule.to_excel(

                writer,

                sheet_name="Depreciation",

                index=False

            )

            pd.DataFrame(

                self.loan_schedule

            ).T.to_excel(

                writer,

                sheet_name="Loan Schedule"

            )
            
            
            self.replacement_schedule.to_excel(

                writer,

                sheet_name="Replacement",

                index=False

            )

        print(
            f"Cash flow exported to {filename}"
        )

    #Export Chart Flow
    def plot_cumulative_cashflow(
        self,
        filename="outputs/figures/cumulative_cashflow.png"
    ):
        """
        Plot cumulative cash flow over project lifetime.
        """
        table = self.calculate_cash_flow()

        os.makedirs(
            os.path.dirname(filename),
            exist_ok=True
        )

        plt.figure(figsize=(10, 6))

        plt.plot(
            table["Year"],
            table["Cumulative Cash Flow (VND)"] / 1e9,
            marker="o"
        )

        plt.axhline(
            y=0,
            linestyle="--"
        )

        payback = self.calculate_payback()

        if payback is not None:

            plt.axvline(
                x=payback,
                linestyle=":"
            )

            plt.text(
                payback,
                0,
                f"Payback ≈ {payback:.2f} yrs"
            )

        plt.title(
            "Cumulative Cash Flow"
        )

        plt.xlabel(
            "Year"
        )

        plt.ylabel(
            "Cumulative Cash Flow (Billion VND)"
        )

        plt.grid(True)
        
        plt.axhline(
            y=0,
            color="black",
            linewidth=1
        )

        plt.tight_layout()

        plt.savefig(
            filename,
            dpi=300,
            bbox_inches="tight"
        )

        plt.close()

        print(
            f"Cumulative cash flow chart saved to {filename}"
        )
    
#Load financial config for easier modify
def load_financial_config(path):
    
    #Load financial input parameters.
    with open(path, "r") as f:
        return json.load(f)
