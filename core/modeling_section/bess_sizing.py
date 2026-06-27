"""
BESS Sizing Based on Sungrow ST225kWh-110kW-2h-AU Datasheet

Purpose:
- Estimate the number of Sungrow BESS units required for target BESS scenarios.
- Check both power requirement and energy requirement.
- Generate outputs for 4MW-2h and 4MW-4h scenarios.

Important:
- This is a datasheet-based sizing calculation.
- It does not replace the official electrical design, SLD, PCS configuration,
  transformer sizing, protection design, or vendor proposal.
"""

from math import ceil
from pathlib import Path

import pandas as pd


def get_project_root() -> Path:
    """
    Return project root based on this file location.

    File location:
        core/modeling_section/bess_sizing.py

    parents[0] = core/modeling_section
    parents[1] = core
    parents[2] = project root
    """
    return Path(__file__).resolve().parents[2]


def size_sungrow_bess(
    scenario_name: str,
    target_power_mw: float,
    target_duration_h: float,
    unit_energy_kwh: float = 229.0,
    unit_power_kw: float = 110.0,
    pcs_max_efficiency_percent: float = 98.6,
    max_parallel_quantity_offgrid: int = 10,
) -> dict:
    """
    Size Sungrow BESS units for a target power-duration scenario.

    Datasheet values:
    - Unit nominal capacity: 229 kWh
    - Unit nominal power: 110 kW
    - PCS max efficiency: 98.6%
    - Max parallel quantity in off-grid mode: <= 10

    Parameters
    ----------
    scenario_name:
        Name of sizing scenario, e.g., "4MW-2h".

    target_power_mw:
        Desired BESS power in MW.

    target_duration_h:
        Desired discharge duration in hours.

    unit_energy_kwh:
        Energy capacity per Sungrow unit.

    unit_power_kw:
        Nominal power per Sungrow unit.

    pcs_max_efficiency_percent:
        PCS max efficiency from datasheet.

    max_parallel_quantity_offgrid:
        Max parallel quantity from datasheet for off-grid mode.
        This is used only as a warning indicator, not as a hard design rule
        for on-grid installations.

    Returns
    -------
    Dictionary containing sizing result.
    """
    target_power_kw = target_power_mw * 1000.0
    target_energy_kwh = target_power_mw * target_duration_h * 1000.0

    units_by_power = ceil(target_power_kw / unit_power_kw)
    units_by_energy = ceil(target_energy_kwh / unit_energy_kwh)

    required_units = max(units_by_power, units_by_energy)

    installed_power_kw = required_units * unit_power_kw
    installed_energy_kwh = required_units * unit_energy_kwh

    installed_power_mw = installed_power_kw / 1000.0
    installed_energy_mwh = installed_energy_kwh / 1000.0

    duration_at_installed_power_h = (
        installed_energy_kwh / installed_power_kw
        if installed_power_kw > 0
        else None
    )

    duration_at_target_power_h = (
        installed_energy_kwh / target_power_kw
        if target_power_kw > 0
        else None
    )

    power_margin_kw = installed_power_kw - target_power_kw
    energy_margin_kwh = installed_energy_kwh - target_energy_kwh

    power_margin_percent = (
        power_margin_kw / target_power_kw * 100.0
        if target_power_kw > 0
        else None
    )

    energy_margin_percent = (
        energy_margin_kwh / target_energy_kwh * 100.0
        if target_energy_kwh > 0
        else None
    )

    if required_units == units_by_power and required_units == units_by_energy:
        limiting_requirement = "power_and_energy"
    elif required_units == units_by_power:
        limiting_requirement = "power"
    else:
        limiting_requirement = "energy"

    if installed_power_kw > target_power_kw * 1.10:
        design_note = (
            "Installed PCS power is significantly higher than target power. "
            "Use export/control limit at target power or request a 4h-specific configuration."
        )
    elif installed_energy_kwh >= target_energy_kwh and installed_power_kw >= target_power_kw:
        design_note = (
            "Sizing satisfies both target power and target energy."
        )
    else:
        design_note = (
            "Sizing does not fully satisfy target; review input parameters."
        )

    offgrid_parallel_warning = required_units > max_parallel_quantity_offgrid

    return {
        "scenario": scenario_name,
        "target_power_mw": target_power_mw,
        "target_duration_h": target_duration_h,
        "target_energy_mwh": target_energy_kwh / 1000.0,
        "unit_energy_kwh": unit_energy_kwh,
        "unit_power_kw": unit_power_kw,
        "pcs_max_efficiency_percent": pcs_max_efficiency_percent,
        "units_by_power": units_by_power,
        "units_by_energy": units_by_energy,
        "required_units": required_units,
        "limiting_requirement": limiting_requirement,
        "installed_power_mw": installed_power_mw,
        "installed_energy_mwh": installed_energy_mwh,
        "duration_at_installed_power_h": duration_at_installed_power_h,
        "duration_at_target_power_h": duration_at_target_power_h,
        "power_margin_kw": power_margin_kw,
        "energy_margin_kwh": energy_margin_kwh,
        "power_margin_percent": power_margin_percent,
        "energy_margin_percent": energy_margin_percent,
        "offgrid_parallel_warning": offgrid_parallel_warning,
        "max_parallel_quantity_offgrid": max_parallel_quantity_offgrid,
        "design_note": design_note,
        "source": "Sungrow ST225kWh-110kW-2h-AU datasheet-based sizing",
    }


def make_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create compact summary for presentation.
    """
    keep_cols = [
        "scenario",
        "target_power_mw",
        "target_duration_h",
        "target_energy_mwh",
        "required_units",
        "limiting_requirement",
        "installed_power_mw",
        "installed_energy_mwh",
        "duration_at_target_power_h",
        "power_margin_percent",
        "energy_margin_percent",
        "offgrid_parallel_warning",
        "design_note",
    ]

    return df[keep_cols].copy()


def main() -> None:
    project_root = get_project_root()
    output_dir = project_root / "outputs" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        size_sungrow_bess(
            scenario_name="4MW-2h",
            target_power_mw=4.0,
            target_duration_h=2.0,
        ),
        size_sungrow_bess(
            scenario_name="4MW-4h",
            target_power_mw=4.0,
            target_duration_h=4.0,
        ),
    ]

    df = pd.DataFrame(scenarios)
    summary = make_summary(df)

    full_path = output_dir / "sungrow_bess_sizing.csv"
    summary_path = output_dir / "sungrow_bess_sizing_summary.csv"

    df.to_csv(full_path, index=False)
    summary.to_csv(summary_path, index=False)

    print(f"Saved {full_path}")
    print(f"Saved {summary_path}")

    print("\nFull sizing result:")
    print(df.to_string(index=False))

    print("\nPresentation summary:")
    print(summary.to_string(index=False))

    print("\nKey proof:")
    row_2h = df[df["scenario"] == "4MW-2h"].iloc[0]
    print(
        f"4MW-2h requires {int(row_2h['required_units'])} units: "
        f"{row_2h['installed_power_mw']:.2f} MW, "
        f"{row_2h['installed_energy_mwh']:.3f} MWh."
    )

    row_4h = df[df["scenario"] == "4MW-4h"].iloc[0]
    print(
        f"4MW-4h requires {int(row_4h['required_units'])} units by energy: "
        f"{row_4h['installed_power_mw']:.2f} MW installed PCS, "
        f"{row_4h['installed_energy_mwh']:.3f} MWh. "
        f"At target 4MW, duration is {row_4h['duration_at_target_power_h']:.2f} h."
    )


if __name__ == "__main__":
    main()