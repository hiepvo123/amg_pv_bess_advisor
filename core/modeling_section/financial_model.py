import numpy as np
import pandas as pd
import numpy_financial as npf
import matplotlib.pyplot as plt
import os
import json

class FinancialModel:

    def __init__(
        self,
        capex,
        opex,
        annual_revenue,
        discount_rate,
        project_life,
        annual_pv_energy=None,
        annual_bess_energy=None,
        bess_capex=None,
        battery_replacement_cost=0,
        battery_replacement_year=10,
        price_growth_rate=0.0
    ):
        
        """
        Parameters
        ----------
        capex : float
            Initial investment (VND)

        opex : float
            Annual operating cost (VND/year)

        annual_revenue : float
            Annual income from electricity (VND/year)

        discount_rate : float
            Discount rate (0.1 = 10%)

        project_life : int
            Project lifetime (years)

        annual_pv_energy : float
            Annual PV generation (kWh/year)

        annual_bess_energy : float
            Annual discharged BESS energy (kWh/year)
        """

        self.capex = capex
        self.opex = opex
        self.revenue = annual_revenue
        self.rate = discount_rate
        self.life = project_life

        self.pv_energy = annual_pv_energy
        self.bess_energy = annual_bess_energy
        self.bess_capex = (
            bess_capex if bess_capex is not None
            else capex
        )

        self.battery_replacement_cost = (
            battery_replacement_cost
        )

        self.battery_replacement_year = (
            battery_replacement_year
        )
        self.price_growth_rate = (
        price_growth_rate
        )
        
        
    def get_revenue_for_year(
        self,
        year
        ):
        return (
            self.revenue *
            (
                1 +
                self.price_growth_rate
            ) ** (year - 1)
        )
        
#Cash Flow
    def calculate_cash_flow(self):
        """
        Create annual cash flow table.
        """

        years = list(range(self.life + 1))

        cashflows = [-self.capex]

        for year in range(1, self.life + 1):

            annual_cf = (
                self.get_revenue_for_year(year) - self.opex
            )

            if year == self.battery_replacement_year:

                annual_cf -= (
                    self.battery_replacement_cost
                )

            cashflows.append(
                annual_cf
            )
        cumulative = np.cumsum(cashflows)

        table = pd.DataFrame({
            "Year": years,
            "Cash Flow (VND)": cashflows,
            "Cumulative Cash Flow (VND)": cumulative
        })

        return table
    #NPV
    def calculate_npv(self):

        annual_cf = self.revenue - self.opex

        npv = -self.capex

        for year in range(1, self.life + 1):
                npv += (
                    annual_cf /
                    ((1 + self.rate) ** year)
                )

        return npv


#IRR
    def calculate_irr(self):
        """
        Internal Rate of Return.
        """

        cashflows = [-self.capex]

        for _ in range(self.life):
            cashflows.append(
                self.revenue - self.opex
            )

        return npf.irr(cashflows)


#Paypack Period
    def calculate_payback(self):

        cash_table = self.calculate_cash_flow()

        for i in range(1, len(cash_table)):

            prev_cf = cash_table.iloc[i-1]["Cumulative Cash Flow (VND)"]
            curr_cf = cash_table.iloc[i]["Cumulative Cash Flow (VND)"]

            if curr_cf >= 0:

                fraction = (
                    abs(prev_cf) /
                    (curr_cf - prev_cf)
                )

                return (
                    (i - 1) + fraction
                )

        return None


#LCOE
    def calculate_lcoe(self):
        """
        Levelized Cost of Energy.
        Unit: VND/kWh
        """
        degradation = 0.005
        if self.pv_energy is None:
            return None

        pv_cost = self.capex

        pv_energy_total = 0


        for year in range(1, self.life + 1):

            discount = (
                1 + self.rate
            ) ** year


            pv_cost += (
                self.opex / discount
            )


            pv_energy_total += (
                self.pv_energy / discount
            )


        return pv_cost / pv_energy_total


#LCOS
    def calculate_lcos(self):
        """
        Levelized Cost of Storage.
        Unit: VND/kWh
        """

        if self.bess_energy is None:
            return None

        bess_cost = self.bess_capex

        discharged_energy = 0

        for year in range(1, self.life + 1):

            discount = (
                1 + self.rate
            ) ** year

            bess_cost += (
                self.opex / discount
            )

            # Battery replacement
            if year == self.battery_replacement_year:

                bess_cost += (
                    self.battery_replacement_cost /
                    discount
                )

            discharged_energy += (
                self.bess_energy /
                discount
            )

        return (
            bess_cost /
            discharged_energy
        )


#Summary
    def calculate_financial_metrics(self):
        """
        Return all financial indicators.
        """

        return {

            "CAPEX (VND)":
                self.capex,

            "OPEX/year (VND)":
                self.opex,

            "Revenue/year (VND)":
                self.revenue,

            "NPV (VND)":
                self.calculate_npv(),

            "IRR (%)":
                self.calculate_irr() * 100,

            "Payback (years)":
                self.calculate_payback(),

            "LCOE (VND/kWh)":
                self.calculate_lcoe(),

            "LCOS (VND/kWh)":
                self.calculate_lcos()
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

        table.to_excel(
            filename,
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