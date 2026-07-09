import numpy as np
import pandas as pd
import numpy_financial as npf
import matplotlib.pyplot as plt
import json
import os


class FinancialModel:

    def __init__(
        self,
        pv_capex,
        inverter_capex,
        other_capex,

        pv_opex,
        bess_opex,

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
        

    ):

        # -----------------------
        # Capital Cost
        # -----------------------

        self.pv_capex = pv_capex or 0
        self.bess_capex = bess_capex or 0
        self.inverter_capex = inverter_capex
        self.other_capex = other_capex

        self.capex = (
            self.pv_capex
            + self.bess_capex
        )

        # -----------------------
        # OPEX
        # -----------------------

        self.pv_opex = pv_opex
        self.bess_opex = bess_opex

        self.pv_result = pv_result
        self.bess_result = bess_result
        
        # -----------------------
        # Energy
        # -----------------------

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

        self.inflation_rate = inflation_rate

        self.pv_degradation_rate = pv_degradation_rate
        self.battery_degradation_rate = battery_degradation_rate
        tax_loss_balance = 0
        # -----------------------
        # Replacement
        # -----------------------

        self.battery_replacement_cost = battery_replacement_cost
        self.battery_replacement_year = battery_replacement_year

        self.inverter_replacement_cost = inverter_replacement_cost
        self.inverter_replacement_year = inverter_replacement_year

        self.salvage_value = salvage_value

        # -----------------------
        # Financing
        # -----------------------

        self.loan_fraction = loan_fraction
        self.loan_interest_rate = loan_interest_rate
        self.loan_term = loan_term

        self.tax_rate = tax_rate

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
        self.validate_inputs()
        self.loan_schedule = self.build_loan_schedule()
        self.capex_schedule = self.build_capex_schedule()
        self.revenue_schedule = self.build_revenue_schedule()
        self.opex_schedule = self.build_opex_schedule()
        self.replacement_schedule = self.build_replacement_schedule()
        self.depreciation_schedule = self.build_depreciation_schedule()
       
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
        """
        Net exported electricity after degradation.
        Returns kWh.
        """

        if self.pv_energy is None:
            return 0

        exported = self.pv_energy * 1000

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
        Used by build_opex_schedule() for variable O&M.
        """

        return self.energy_schedule.loc[
            self.energy_schedule["Year"] == year,
            "PV Energy (kWh)"
        ].iloc[0]
        
        
    #SCHEDULE
    
    def build_capex_schedule(self):
        """
        Build capital cost breakdown similar to SAM.
        """

        rows = []

        rows.append({
            "Component": "PV Modules",
            "Cost (VND)": self.pv_capex
        })

        rows.append({
            "Component": "Battery System",
            "Cost (VND)": self.bess_capex
        })

        rows.append({
            "Component": "Inverter",
            "Cost (VND)": self.inverter_capex
        })

        rows.append({
            "Component": "Other BOS",
            "Cost (VND)": self.other_capex
        })

        rows.append({
            "Component": "Total Installed Cost",
            "Cost (VND)": self.capex
        })

        rows.append({
            "Component": "Debt",
            "Cost (VND)": self.capex * self.loan_fraction
        })

        rows.append({
            "Component": "Equity",
            "Cost (VND)": self.capex * (1-self.loan_fraction)
        })

        return pd.DataFrame(rows)
    
    
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

            bess_energy = (
                self.bess_energy
                *
                (
                    (1 - self.battery_degradation_rate)
                    ** (year - 1)
                )
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
        """
        Build annual electricity revenue schedule.
        Similar to SAM Revenue table.

        Revenue is earned on total energy delivered to the offtaker,
        i.e. PV energy exported directly PLUS BESS energy discharged
        (both already after degradation, from energy_schedule's
        "Total Energy (kWh)" column). Using PV energy alone would
        silently drop all BESS-sourced revenue whenever a battery is
        present -- see build_energy_schedule()'s docstring, which
        already documents "Total Energy" as the intended source for
        this schedule.
        """

        rows = []

        for year in range(1, self.life + 1):

            row = self.energy_schedule.loc[
                self.energy_schedule["Year"] == year
            ].iloc[0]

            pv_energy = row["PV Energy (kWh)"]
            bess_energy = row["BESS Energy (kWh)"]
            energy = row["Total Energy (kWh)"]

            # Electricity price
            price = (
                self.electricity_price
                *
                (1 + self.price_growth_rate) ** (year - 1)
            )

            revenue = energy * price

            rows.append({

                "Year": year,

                "PV Energy (kWh)": pv_energy,

                "BESS Energy (kWh)": bess_energy,

                "Total Energy (kWh)": energy,

                "Electricity Price (VND/kWh)": price,

                "Revenue (VND)": revenue

            })

        return pd.DataFrame(rows)
    
    def build_opex_schedule(self):
        """
        Build annual operating cost schedule.
        Similar to SAM Operating Expenses table.
        """

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

            variable = (
                self.variable_opex_rate
                * self.get_pv_energy_for_year(year)
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
        """
        Build depreciation schedule similar to NREL SAM.

        Includes:
            - Base system depreciation
            - Battery replacement depreciation
            - Inverter replacement depreciation
            - Book value
        """

        rows = []

        asset_value = self.capex

        accumulated = 0

        # --------------------------
        # Base depreciation rates
        # --------------------------

        if self.depreciation_method.upper() == "SL":

            base_rate = 1 / self.depreciation_years

            base_rates = [base_rate] * self.depreciation_years

        elif self.depreciation_method.upper() == "MACRS":

            base_rates = [
                0.20,
                0.32,
                0.192,
                0.1152,
                0.1152,
                0.0576
            ]

        else:

            raise ValueError(
                "Unknown depreciation method."
            )

        # --------------------------
        # Build year by year
        # --------------------------

        for year in range(1, self.life + 1):

            # --------------------------
            # Base depreciation
            # --------------------------

            if year <= len(base_rates):

                base_dep = asset_value * base_rates[year - 1]

                dep_rate = base_rates[year - 1] * 100

            else:

                base_dep = 0

                dep_rate = 0

            # --------------------------
            # Battery depreciation
            # --------------------------
            
            battery_dep = 0

            for _, row in self.replacement_schedule.iterrows():

                install_year = row["Year"]

                replacement_cost = row["Battery Replacement (VND)"]

                if replacement_cost == 0:
                    continue

                age = year - install_year

                if 0 <= age < self.depreciation_years:

                    battery_dep += (
                        row["Battery Replacement (VND)"]
                        /
                        self.depreciation_years
                    )

            # --------------------------
            # Inverter depreciation
            # --------------------------

            inverter_dep = 0

            for _, row in self.replacement_schedule.iterrows():

                install_year = row["Year"]

                replacement_cost = row["Inverter Replacement (VND)"]

                if replacement_cost == 0:
                    continue

                age = year - install_year

                if 0 <= age < self.depreciation_years:

                    inverter_dep += (

                        replacement_cost

                        / self.depreciation_years

                    )

            # --------------------------
            # Total
            # --------------------------

            total_dep = (

                base_dep

                + battery_dep

                + inverter_dep

            )

            accumulated += total_dep

            book_value = max(

                asset_value
                + self.battery_replacement_cost
                + self.inverter_replacement_cost
                - accumulated,

                0

            )

            rows.append({

                "Year": year,

                "Depreciation Rate (%)": dep_rate,

                "Asset Value (VND)": asset_value,

                "Base Depreciation (VND)": base_dep,

                "Battery Depreciation (VND)": battery_dep,

                "Inverter Depreciation (VND)": inverter_dep,

                "Total Depreciation (VND)": total_dep,

                "Accumulated Depreciation (VND)": accumulated,

                "Book Value (VND)": book_value

            })

        return pd.DataFrame(rows)
    
    def build_replacement_schedule(self):
        """
        Build replacement schedule.

        Similar to SAM's Replacement Costs table.
        """

        rows = []

        for year in range(1, self.life + 1):

            battery_cost = 0

            inverter_cost = 0

            if year == self.battery_replacement_year:

                battery_cost = self.battery_replacement_cost

            if year == self.inverter_replacement_year:

                inverter_cost = self.inverter_replacement_cost

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
        """
        Build annual amortized loan schedule.
        """
        if self.loan_fraction == 0:
            return {}
        loan_amount = self.capex * self.loan_fraction

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
        """
        Depreciation from replacement assets (battery/inverter).
        Straight-line over remaining depreciation life.
        """

        depreciation = 0

        for start_year, annual_dep, years_left in self.replacement_depreciation.values():

            if start_year <= year < start_year + years_left:
                depreciation += annual_dep

        return depreciation
    
    @staticmethod
    def _infer_interval_hours(df, datetime_col="datetime", default_hours=0.5):
        """
        Infer the simulation timestep (in hours) from a datetime column,
        so power series (MW/kW) can be converted to energy without
        assuming a fixed 30-minute resolution. The assignment allows
        5/15/30-minute or 1-hour timesteps, so this must not be hardcoded.
        Falls back to `default_hours` if there is no usable timestamp.
        """
        if datetime_col not in df.columns or len(df) < 2:
            return default_hours

        ts = pd.to_datetime(df[datetime_col]).sort_values()
        diffs = ts.diff().dropna().dt.total_seconds() / 3600.0

        if diffs.empty:
            return default_hours

        return diffs.median()

    def initialize_energy_inputs(self):
        """
        Calculate annualized energy from PV/BESS simulation results.
        Works for partial-year datasets.
        """

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

            # energy_out_kwh is already energy per interval (not power),
            # so no interval-hours multiplication is needed here -- only
            # the day count (for annualization) must be resolution-aware.
            if "date" in self.bess_result.columns:
                days = self.bess_result["date"].nunique()
            elif "datetime" in self.bess_result.columns:
                days = (
                    pd.to_datetime(self.bess_result["datetime"])
                    .dt.date.nunique()
                )
            else:
                # No timestamp column available: fall back to assuming
                # 30-minute resolution (48 rows/day), same as before.
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

            # OPEX escalates with opex_growth_rate, same as build_opex_schedule(),
            # so LCOE stays consistent with the OPEX actually charged in the
            # cash flow / NPV calculation.
            opex_growth = (1 + self.opex_growth_rate) ** (year - 1)

            total += (
                self.pv_opex * opex_growth
                /
                discount
            )

            if year == self.inverter_replacement_year:
                total += (
                    self.inverter_replacement_cost
                    / discount
                )

        # Salvage value reduces lifecycle cost
        total -= (
            self.salvage_value
            * (1 - self.tax_rate) / discount
        )

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

            if year == self.battery_replacement_year:

                total += (
                    self.battery_replacement_cost
                    /
                    discount
                )

        return total

    def present_value_total_opex(self):
        """
        NPV of total operating costs (Total O&M, all components) over the
        project life, discounted at the nominal discount rate -- consistent
        with how the equity cash flow / project NPV is discounted.
        Used for the "Lifetime OPEX (NPV)" summary metric.
        """

        total = 0

        for year in range(1, self.life + 1):

            opex = self.get_opex_for_year(year)

            discount = (1 + self.discount_rate) ** year

            total += opex / discount

        return total

    def validate_inputs(self):

        assert self.capex > 0

        assert self.life > 0

        assert self.discount_rate >= 0

        assert self.loan_fraction >= 0

        assert self.loan_fraction <= 1

        assert self.tax_rate >= 0

        assert self.tax_rate <= 1
        
        
    def present_value_discharged_bess_energy(self):

        total = 0

        for year in range(1, self.life + 1):

            energy = (
                self.bess_energy
                *
                ((1 - self.battery_degradation_rate) ** (year - 1))
            )

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


#Cash Flow
    def calculate_cash_flow(self):
        """
        SAM-style after-tax equity cash flow.
        """

        rows = []
        tax_loss_balance = 0

        # Initial equity investment
        debt = self.capex * self.loan_fraction
        equity = self.capex_schedule.loc[
            self.capex_schedule["Component"]=="Equity",
            "Cost (VND)"
        ].iloc[0]

        cumulative = -equity

        rows.append({

            "Year":0,

            "Energy (kWh)":0,

            "Revenue (VND)":0,

            "OPEX (VND)":0,

            "EBITDA (VND)":0,

            "Depreciation (VND)":0,

            "EBIT (VND)":0,

            "Interest (VND)":0,

            "Taxable Income (VND)":0,

            "Income Tax (VND)":0,

            "Net Income (VND)":0,

            "Principal (VND)":0,

            "Replacement (VND)":0,

            "Salvage (VND)":0,

            "Equity Cash Flow (VND)":-equity,

            "Discount Factor":1,

            "Discounted Cash Flow (VND)":-equity,

            "Cumulative Cash Flow (VND)":cumulative

        })

        for year in range(1,self.life+1):
            # ------------------------
            # Energy
            # ------------------------

            energy = self.energy_schedule.loc[
                self.energy_schedule["Year"] == year,
                "Total Energy (kWh)"
            ].iloc[0]

            # ------------------------
            # Revenue
            # ------------------------

            revenue = self.revenue_schedule.loc[
                self.revenue_schedule["Year"] == year,
                "Revenue (VND)"
            ].iloc[0]

            # ------------------------
            # Operating Cost
            # ------------------------

            opex = self.opex_schedule.loc[
                self.opex_schedule["Year"] == year,
                "Total O&M (VND)"
            ].iloc[0]

            # ------------------------
            # EBITDA
            # ------------------------

            EBITDA = revenue - opex

            # ------------------------
            # Depreciation
            # ------------------------

            depreciation = (
                self.depreciation_schedule.loc[
                    self.depreciation_schedule["Year"] == year,
                    "Total Depreciation (VND)"
                ]
                .iloc[0]
            )

            # ------------------------
            # EBIT
            # ------------------------

            EBIT = EBITDA - depreciation

            # ------------------------
            # Financing
            # ------------------------

            loan = self.loan_schedule.get(
                year,
                {"interest": 0, "principal": 0, "balance": 0}
            )

            interest = loan["interest"]

            principal = loan["principal"]

            loan_balance = loan["balance"]
                
            # ------------------------
            # Taxable income
            # ------------------------

            taxable_income = (
                EBIT
                - interest
            )

            if tax_loss_balance > 0:
                offset = min(taxable_income, tax_loss_balance)
                taxable_income -= offset
                tax_loss_balance -= offset

            if taxable_income < 0:

                tax_loss_balance += abs(taxable_income)

                taxable_income = 0

            income_tax = (
                taxable_income
                * self.tax_rate
            )

            # ------------------------
            # Net income
            # ------------------------

            net_income = (
                EBIT
                - interest
                - income_tax
            )

            # ------------------------
            # Replacement
            # ------------------------
            replacement = (
                self.replacement_schedule.loc[
                    self.replacement_schedule["Year"] == year,
                    "Total Replacement (VND)"
                ]
                .iloc[0]
            )

            # ------------------------
            # Salvage
            # ------------------------

            salvage = 0

            if year == self.life:

                salvage = self.salvage_value * (1 - self.tax_rate)

            # ------------------------
            # Operating Cash Flow
            # ------------------------

            operating_cf = (

                net_income

                + depreciation

            )

            # ------------------------
            # Project Cash Flow
            # ------------------------

            project_cf = (

                operating_cf

                - replacement

                + salvage

            )

            # ------------------------
            # Equity Cash Flow
            # ------------------------

            equity_cf = (

                project_cf

                - principal

            )

            discount = (

                1

                /

                (

                    (1+self.discount_rate)

                    **

                    year

                )

            )

            discounted_cf = equity_cf * discount

            cumulative += discounted_cf

            rows.append({

                "Year":year,

                "Energy (kWh)":energy,

                "Revenue (VND)":revenue,

                "OPEX (VND)":opex,

                "EBITDA (VND)":EBITDA,

                "Depreciation (VND)":depreciation,

                "EBIT (VND)":EBIT,

                "Interest (VND)":interest,

                "Taxable Income (VND)":taxable_income,

                "Income Tax (VND)":income_tax,

                "Net Income (VND)":net_income,

                "Principal (VND)":principal,
                
                "Loan Balance (VND)": loan_balance,

                "Replacement (VND)":replacement,

                "Salvage (VND)":salvage,

                "Equity Cash Flow (VND)":equity_cf,

                "Discount Factor":discount,

                "Discounted Cash Flow (VND)":discounted_cf,

                "Cumulative Cash Flow (VND)":cumulative,
                
                "Operating Cash Flow (VND)": operating_cf,

                "Project Cash Flow (VND)": project_cf

            })

        return pd.DataFrame(rows)
    
    #NPV
    def calculate_npv(self):
        "Net Present Value"
        cashflow = self.calculate_cash_flow()

        return cashflow[
            "Discounted Cash Flow (VND)"
        ].sum()


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
        Discounted Payback Period
        """

        cashflow = self.calculate_cash_flow()

        cumulative = 0.0

        for _, row in cashflow.iterrows():

            year = row["Year"]

            cf = row["Equity Cash Flow (VND)"]

            discounted_cf = cf / (
                (1 + self.discount_rate) ** year
            )

            previous = cumulative

            cumulative += discounted_cf

            if cumulative >= 0:

                if year == 0:
                    return 0

                return (
                    (year - 1)
                    + abs(previous) / discounted_cf
                )

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


#Summary
    def calculate_financial_metrics(self):
        """
        Return all financial indicators.
        """

        return {

            # -----------------------
            # CAPEX
            # -----------------------

            "PV CAPEX (VND)": self.pv_capex,

            "BESS CAPEX (VND)": self.bess_capex,

            "Total CAPEX (VND)": self.capex,

            "Equity Investment (VND)": self.capex * (1-self.loan_fraction),

            "Debt Amount (VND)": self.capex * self.loan_fraction,

            "Debt Fraction (%)": self.loan_fraction * 100,

            # -----------------------
            # OPEX
            # -----------------------

            "Year 1 OPEX (VND)": self.get_opex_for_year(1),

            "Lifetime OPEX, NPV (VND)": self.present_value_total_opex(),

            # -----------------------
            # Revenue (context, not one of the core 7 metrics)
            # -----------------------

            "Year 1 Revenue (VND)": self.get_revenue_for_year(1),

            # -----------------------
            # Core financial metrics
            # -----------------------

            "NPV (VND)": self.calculate_npv(),

            "IRR (%)": self.calculate_irr()*100,

            "Payback (Years)": self.calculate_payback(),

            "LCOE (VND/kWh)": self.calculate_lcoe(),

            "LCOS (VND/kWh)": self.calculate_lcos()

        }

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

            ("FINANCING", "", ""),
            ("Equity", m["Equity Investment (VND)"], "VND"),
            ("Size of debt", m["Debt Amount (VND)"], "VND"),
            ("Debt fraction", m["Debt Fraction (%)"], "%"),

            ("OPERATING COSTS", "", ""),
            ("Year 1 OPEX", m["Year 1 OPEX (VND)"], "VND"),
            ("Lifetime OPEX (NPV)", m["Lifetime OPEX, NPV (VND)"], "VND"),

            ("KEY METRICS", "", ""),
            ("NPV", m["NPV (VND)"], "VND"),
            ("IRR", m["IRR (%)"], "%"),
            ("Payback period", m["Payback (Years)"], "years"),
            ("LCOE, nominal", m["LCOE (VND/kWh)"], "VND/kWh"),
            ("LCOS, nominal", m["LCOS (VND/kWh)"], "VND/kWh"),
        ]

    #Print Summary (SAM-style)
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

        lines.append("")
        lines.append("OPERATING COSTS (OPEX)")
        lines.append(f"  {'Year 1 OPEX':<28}: {money(m['Year 1 OPEX (VND)'])}")
        lines.append(f"  {'Lifetime OPEX (NPV)':<28}: {money(m['Lifetime OPEX, NPV (VND)'])}")

        lines.append("")
        lines.append("KEY METRICS")
        lines.append(f"  {'NPV':<28}: {money(m['NPV (VND)'])}")
        lines.append(f"  {'IRR':<28}: {pct(m['IRR (%)'])}")
        lines.append(f"  {'Payback Period':<28}: {years(m['Payback (Years)'])}")
        lines.append(f"  {'LCOE':<28}: {per_kwh(m['LCOE (VND/kWh)'])}")
        lines.append(f"  {'LCOS':<28}: {per_kwh(m['LCOS (VND/kWh)'])}")

        lines.append("=" * 60)

        report = "\n".join(lines)
        print(report)

        return report

    def build_financial_summary(self):
        """
        Final financial summary similar to NREL SAM.
        """

        summary = {

            # ------------------------
            # Capital Cost
            # ------------------------
            "PV CAPEX (VND)": self.pv_capex,
            "BESS CAPEX (VND)": self.bess_capex,
            "Inverter CAPEX (VND)": self.inverter_capex,
            "Other CAPEX (VND)": self.other_capex,
            "Total CAPEX (VND)": self.capex,

            # ------------------------
            # OPEX
            # ------------------------
            "Year 1 PV OPEX (VND)": self.pv_opex,
            "Year 1 BESS OPEX (VND)": self.bess_opex,
            "Year 1 Total OPEX (VND)": self.pv_opex + self.bess_opex,

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
            "Debt (VND)": self.capex * self.loan_fraction,
            "Equity (VND)": self.capex * (1 - self.loan_fraction),

            # ------------------------
            # Financial Indicators
            # ------------------------
            "NPV (VND)": self.calculate_npv(),
            "IRR (%)": self.calculate_irr() * 100,
            "Payback (Years)": self.calculate_payback(),
            "LCOE (VND/kWh)": self.calculate_lcoe(),
            "LCOS (VND/kWh)": self.calculate_lcos()
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