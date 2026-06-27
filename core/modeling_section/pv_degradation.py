"""
PV Degradation Model Based on LONGi Hi-MO 5 Datasheet

Purpose:
- Simulate PV module degradation over 30 years using datasheet warranty values.
- Generate remaining capacity, aging loss, and remaining Pmax for 530/540/550 Wp modules.
- Provide a clear baseline for long-term degradation analysis.

Important:
- This is a datasheet-based simulation.
- It is NOT measured degradation from the 2-month operational dataset.
- Real degradation requires multi-year measured data, cleaning/maintenance logs,
  inverter/string data, IV curve, EL test, or thermal inspection.
"""

from pathlib import Path

import pandas as pd


def get_project_root() -> Path:
    """
    Return project root based on this file location.

    File location:
        core/modeling_section/pv_degradation.py

    parents[0] = core/modeling_section
    parents[1] = core
    parents[2] = project root
    """
    return Path(__file__).resolve().parents[2]


def simulate_longi_degradation(
    p_initial_wp: float,
    first_year_degradation_percent: float = 2.0,
    annual_degradation_after_year1_percent: float = 0.45,
    years: int = 30,
    plant_capacity_mwp: float = 47.5,
) -> pd.DataFrame:
    """
    Simulate LONGi Hi-MO 5 LR5-72HBD degradation.

    Datasheet-based assumptions:
    - First-year degradation: < 2%
    - Year 2 to Year 30 degradation: 0.45% per year
    - 30-year linear power warranty

    Parameters
    ----------
    p_initial_wp:
        Initial module power, e.g. 530, 540, or 550 Wp.

    first_year_degradation_percent:
        Worst-case first-year degradation.
        Datasheet says <2%, so we use 2% as conservative value.

    annual_degradation_after_year1_percent:
        Annual degradation from year 2 to year 30.

    years:
        Simulation horizon.

    plant_capacity_mwp:
        Assumed plant DC capacity in MWp.

    Returns
    -------
    DataFrame with yearly degradation values.
    """
    rows = []

    for year in range(years + 1):
        if year == 0:
            remaining_capacity_percent = 100.0
            annual_degradation_percent = 0.0
        elif year == 1:
            remaining_capacity_percent = 100.0 - first_year_degradation_percent
            annual_degradation_percent = first_year_degradation_percent
        else:
            remaining_capacity_percent = (
                100.0
                - first_year_degradation_percent
                - (year - 1) * annual_degradation_after_year1_percent
            )
            annual_degradation_percent = annual_degradation_after_year1_percent

        remaining_capacity_percent = max(0.0, remaining_capacity_percent)

        aging_loss_percent = 100.0 - remaining_capacity_percent
        remaining_pmax_wp = p_initial_wp * remaining_capacity_percent / 100.0

        plant_remaining_capacity_mwp = (
            plant_capacity_mwp * remaining_capacity_percent / 100.0
        )

        estimated_module_count = (
            plant_capacity_mwp * 1_000_000.0 / p_initial_wp
            if p_initial_wp > 0
            else None
        )

        rows.append(
            {
                "year": year,
                "initial_Pmax_Wp": p_initial_wp,
                "remaining_capacity_percent": remaining_capacity_percent,
                "aging_loss_percent": aging_loss_percent,
                "remaining_Pmax_Wp": remaining_pmax_wp,
                "annual_degradation_percent": annual_degradation_percent,
                "plant_initial_capacity_MWp": plant_capacity_mwp,
                "plant_remaining_capacity_MWp": plant_remaining_capacity_mwp,
                "estimated_module_count": estimated_module_count,
                "source": "LONGi Hi-MO 5 LR5-72HBD datasheet-based warranty simulation",
                "note": (
                    "Datasheet-based degradation model only; "
                    "not measured field degradation."
                ),
            }
        )

    return pd.DataFrame(rows)


def make_degradation_summary(all_results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Create compact summary at selected years for presentation.
    """
    selected_years = [0, 1, 5, 10, 15, 20, 25, 30]
    rows = []

    for scenario_name, df in all_results.items():
        selected = df[df["year"].isin(selected_years)].copy()

        for _, row in selected.iterrows():
            rows.append(
                {
                    "scenario": scenario_name,
                    "year": int(row["year"]),
                    "initial_Pmax_Wp": row["initial_Pmax_Wp"],
                    "remaining_capacity_percent": row[
                        "remaining_capacity_percent"
                    ],
                    "aging_loss_percent": row["aging_loss_percent"],
                    "remaining_Pmax_Wp": row["remaining_Pmax_Wp"],
                    "plant_remaining_capacity_MWp": row[
                        "plant_remaining_capacity_MWp"
                    ],
                    "estimated_module_count": row["estimated_module_count"],
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    project_root = get_project_root()
    output_dir = project_root / "outputs" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    module_powers_wp = [530.0, 540.0, 550.0]
    all_results = {}

    for p_initial_wp in module_powers_wp:
        df = simulate_longi_degradation(
            p_initial_wp=p_initial_wp,
            first_year_degradation_percent=2.0,
            annual_degradation_after_year1_percent=0.45,
            years=30,
            plant_capacity_mwp=47.5,
        )

        scenario_name = f"{int(p_initial_wp)}Wp"
        all_results[scenario_name] = df

        out_path = output_dir / f"longi_degradation_{int(p_initial_wp)}Wp.csv"
        df.to_csv(out_path, index=False)
        print(f"Saved {out_path}")

    summary = make_degradation_summary(all_results)
    summary_path = output_dir / "longi_degradation_summary.csv"
    summary.to_csv(summary_path, index=False)

    print(f"Saved {summary_path}")

    print("\nQuick presentation summary:")
    print(summary.to_string(index=False))

    print("\nKey proof:")
    year30_540 = all_results["540Wp"].loc[
        all_results["540Wp"]["year"] == 30
    ].iloc[0]

    print(
        f"540Wp module at year 30: "
        f"remaining capacity = {year30_540['remaining_capacity_percent']:.2f}%, "
        f"remaining Pmax = {year30_540['remaining_Pmax_Wp']:.2f} Wp"
    )


if __name__ == "__main__":
    main()