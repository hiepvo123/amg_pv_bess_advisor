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

        discount_rate,
        project_life,

        annual_pv_energy=None,
        annual_bess_energy=None,

        bess_capex=0,

        battery_replacement_cost=0,
        battery_replacement_year=10,
        battery_degradation_rate=0.02,

        inverter_replacement_cost=0,
        inverter_replacement_year=12,

        price_growth_rate=0.0,
        opex_growth_rate=0.02,

        pv_degradation_rate=0.005,

        salvage_value=0,

        loan_fraction=0.70,
        loan_interest_rate=0.08,
        loan_term=20,

        tax_rate=0.20,

        inflation_rate=0.025,

        depreciation_years=20,
        depreciation_method="SL",

        electricity_price=1284

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

        # -----------------------
        # Energy
        # -----------------------

        self.pv_energy = (
            float(annual_pv_energy)
            if annual_pv_energy is not None
            else 0
        )

        self.bess_energy = (
            float(annual_bess_energy)
            if annual_bess_energy is not None
            else 0
        )

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

        self.electricity_price = electricity_price

        self.price_growth_rate = price_growth_rate
        self.opex_growth_rate = opex_growth_rate

        self.inflation_rate = inflation_rate

        self.pv_degradation_rate = pv_degradation_rate
        self.battery_degradation_rate = battery_degradation_rate
        self.tax_loss_balance = 0
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

        # -----------------------
        # Build schedules
        # -----------------------

        self.loan_schedule = self.build_loan_schedule()

        self.validate_inputs()
        
        self.depreciation_schedule = (
            self.build_depreciation_schedule()
        )
        
       
    def get_depreciation(self, year):

        return self.depreciation_schedule.get(year, 0)


    def get_interest_payment(self, year):

        if year in self.loan_schedule:
            return self.loan_schedule[year]["interest"]

        return 0
    def get_principal_payment(self, year):

        if year in self.loan_schedule:
            return self.loan_schedule[year]["principal"]

        return 0
    
    def get_revenue_for_year(self, year):
        """
        Annual electricity revenue after
        PV degradation and electricity price escalation.
        """

        energy = self.get_pv_energy_for_year(year)

        if energy is None:
            return 0

        price = (
            self.electricity_price
            * ((1 + self.price_growth_rate) ** (year - 1))
        )

        return energy * price

    def get_opex_for_year(self, year):
        """
        Annual OPEX after escalation.
        """

        growth = (
            (1 + self.opex_growth_rate)
            ** (year - 1)
        )

        return (
            self.pv_opex
            + self.bess_opex
    ) * growth
        
    def build_depreciation_schedule(self):
        """
        Build annual depreciation schedule.
        Supports:
            - Straight Line (SL)
            - MACRS 5-year
        """

        schedule = {}

        # Straight Line
        if self.depreciation_method.upper() == "SL":

            annual_dep = self.capex / self.depreciation_years

            for year in range(1, self.life + 1):

                if year <= self.depreciation_years:
                    schedule[year] = annual_dep
                else:
                    schedule[year] = 0

        # MACRS 5-year
        elif self.depreciation_method.upper() == "MACRS":

            rates = [
                0.20,
                0.32,
                0.192,
                0.1152,
                0.1152,
                0.0576
            ]

            for year in range(1, self.life + 1):

                if year <= len(rates):
                    schedule[year] = self.capex * rates[year - 1]
                else:
                    schedule[year] = 0

        else:
            raise ValueError(
                "Depreciation method must be 'SL' or 'MACRS'"
            )

        return schedule
    
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

    def get_pv_energy_for_year(self, year):
        """
        PV energy after degradation.
        """

        if self.pv_energy is None:
            return None

        return (
            self.pv_energy *
            ((1 - self.pv_degradation_rate) ** (year - 1))
        )
    
    #HELPER FUNCTION
    def present_value_total_pv_cost(self):

        total = (
        self.pv_capex
        +
        self.inverter_capex
        +
        self.other_capex
    )

        for year in range(1, self.life + 1):

            discount = (1 + self.real_discount_rate) ** year

            total += (
                self.pv_opex
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

            total += (
                self.bess_opex
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

        cost = 0

        if year == self.battery_replacement_year:

            cost += self.battery_replacement_cost

        if year == self.inverter_replacement_year:

            cost += self.inverter_replacement_cost

        return cost


#Cash Flow
    def calculate_cash_flow(self):
        """
        SAM-style after-tax equity cash flow.
        """

        rows = []

        # Initial equity investment
        equity = self.capex * (1 - self.loan_fraction)

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

            energy = self.get_pv_energy_for_year(year)

            # ------------------------
            # Revenue
            # ------------------------

            revenue = self.get_revenue_for_year(year)

            # ------------------------
            # Operating Cost
            # ------------------------

            opex = self.get_opex_for_year(year)

            # ------------------------
            # EBITDA
            # ------------------------

            EBITDA = revenue - opex

            # ------------------------
            # Depreciation
            # ------------------------

            depreciation = self.get_depreciation(year)

            # ------------------------
            # EBIT
            # ------------------------

            EBIT = EBITDA - depreciation

            # ------------------------
            # Financing
            # ------------------------

            interest = self.get_interest_payment(year)

            principal = self.get_principal_payment(year)

            loan_balance = 0

            if year in self.loan_schedule:

                loan_balance = self.loan_schedule[year]["balance"]
                
            # ------------------------
            # Taxable income
            # ------------------------

            taxable_income = (
                EBIT
                - interest
            )

            taxable_income -= self.tax_loss_balance

            if taxable_income < 0:

                self.tax_loss_balance = abs(taxable_income)

                taxable_income = 0

            else:

                self.tax_loss_balance = 0

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

            replacement = self.get_replacement_cost(year)

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

            cumulative += equity_cf

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
        Discounted Payback Period (years)
        """

        cash_table = self.calculate_cash_flow()

        cumulative = 0

        for year in range(len(cash_table)):

            cf = cash_table.iloc[year]["Equity Cash Flow (VND)"]

            discounted_cf = (
                cf /
                ((1 + self.discount_rate) ** year)
            )

            previous = cumulative

            cumulative += discounted_cf

            if cumulative >= 0:

                if year == 0:
                    return 0

                fraction = (
                    abs(previous)
                    /
                    discounted_cf
                )

                return (
                    (year - 1)
                    + fraction
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

            "Total CAPEX (VND)": self.capex,

            "Equity Investment (VND)": self.capex * (1-self.loan_fraction),

            "Debt Amount (VND)": self.capex * self.loan_fraction,

            "Year 1 Revenue (VND)": self.get_revenue_for_year(1),

            "Year 1 OPEX (VND)": self.get_opex_for_year(1),

            "NPV (VND)": self.calculate_npv(),

            "IRR (%)": self.calculate_irr()*100,

            "Payback (Years)": self.calculate_payback(),

            "LCOE (VND/kWh)": self.calculate_lcoe(),

            "LCOS (VND/kWh)": self.calculate_lcos()

        }

#Export Result
    def export_cashflow_excel(
        self,
        filename="outputs/cashflow.xlsx"
    ):
        """
        Export cash flow table to Excel.
        """

        table = self.calculate_cash_flow()

        with pd.ExcelWriter(filename) as writer:

            table.to_excel(

                writer,

                sheet_name="Cash Flow",

                index=False

            )

            pd.DataFrame(

                self.loan_schedule

            ).T.to_excel(

                writer,

                sheet_name="Loan Schedule"

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