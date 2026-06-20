import numpy as np
import pandas as pd
import numpy_financial as npf


class FinancialModel:

    def __init__(
        self,
        capex,
        opex,
        annual_revenue,
        discount_rate,
        project_life,
        annual_pv_energy=None,
        annual_bess_energy=None
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


#Cash Flow
    def calculate_cash_flow(self):
        """
        Create annual cash flow table.
        """

        years = list(range(self.life + 1))

        cashflows = [-self.capex]

        for _ in range(self.life):
            cashflows.append(
                self.revenue - self.opex
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
        """
        Net Present Value.
        """

        cashflows = [-self.capex]

        for _ in range(self.life):
            cashflows.append(
                self.revenue - self.opex
            )

        return npf.npv(
            self.rate,
            cashflows
        )


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
        """
        Return payback year.
        """

        cash_table = self.calculate_cash_flow()

        for _, row in cash_table.iterrows():

            if row["Cumulative Cash Flow (VND)"] >= 0:
                return int(row["Year"])

        return None


#LCORE
    def calculate_lcoe(self):
        """
        Levelized Cost of Energy.
        Unit: VND/kWh
        """

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


        bess_cost = self.capex

        discharged_energy = 0


        for year in range(1, self.life + 1):

            discount = (
                1 + self.rate
            ) ** year


            bess_cost += (
                self.opex / discount
            )


            discharged_energy += (
                self.bess_energy / discount
            )


        return bess_cost / discharged_energy


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


#Test
if __name__ == "__main__":

    model = FinancialModel(
        capex=43e9,
        opex=500e6,
        annual_revenue=9e9,
        discount_rate=0.10,
        project_life=20,
        annual_pv_energy=50e6,
        annual_bess_energy=5e6
    )


    print("\n===== Financial Results =====\n")

    results = model.calculate_financial_metrics()


    for key, value in results.items():
        print(
            f"{key}: {value:,.2f}"
        )


    model.export_cashflow_excel()