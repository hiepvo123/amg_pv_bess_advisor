"""
Supervisor Summary Report Generator

Purpose:
- Combine PV loss KPI, anomaly summary, LONGi degradation, and Sungrow BESS sizing
  into one supervisor-friendly Markdown report.
- Generate a task completion summary CSV.

Inputs:
- outputs/metrics/pv_loss_kpi_summary.csv
- outputs/metrics/pv_anomaly_summary.csv
- outputs/metrics/longi_degradation_summary.csv
- outputs/metrics/sungrow_bess_sizing_summary.csv

Outputs:
- outputs/reports/supervisor_summary.md
- outputs/metrics/task_completion_summary.csv
"""

from pathlib import Path

import pandas as pd


def get_project_root() -> Path:
    """
    File location:
        core/reporting_section/supervisor_summary.py

    parents[0] = core/reporting_section
    parents[1] = core
    parents[2] = project root
    """
    return Path(__file__).resolve().parents[2]


def read_csv_required(path: Path) -> pd.DataFrame:
    """
    Read a required CSV file and raise a clear error if missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}\n"
            "Please run previous checkpoints before generating supervisor summary."
        )
    return pd.read_csv(path)


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """
    Convert DataFrame to simple Markdown table without requiring tabulate.
    """
    if max_rows is not None:
        df = df.head(max_rows)

    if df.empty:
        return "_No data available._"

    df = df.copy()

    # Format floats for readability.
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")

    headers = list(df.columns)
    lines = []

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for _, row in df.iterrows():
        values = [str(row[col]) for col in headers]
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def extract_kpi_values(kpi_df: pd.DataFrame) -> dict:
    """
    Extract key KPI values for quick explanation.
    """
    overall = kpi_df[kpi_df["scope"] == "overall_valid_kpi"]

    if overall.empty:
        return {
            "valid_rows": None,
            "overall_energy_loss_percent": None,
            "overall_pr_proxy": None,
        }

    row = overall.iloc[0]

    return {
        "valid_rows": int(row["rows"]),
        "overall_energy_loss_percent": float(row["energy_loss_percent"]),
        "overall_pr_proxy": float(row["avg_pr_proxy"]),
        "overall_expected_mwh": float(row["energy_expected_mwh"]),
        "overall_measured_mwh": float(row["energy_measured_mwh"]),
    }


def extract_degradation_values(deg_df: pd.DataFrame) -> dict:
    """
    Extract 540Wp Year 30 degradation result.
    """
    case = deg_df[
        (deg_df["scenario"] == "540Wp")
        & (deg_df["year"] == 30)
    ]

    if case.empty:
        return {
            "year30_remaining_capacity_percent": None,
            "year30_remaining_pmax_wp": None,
            "year30_plant_remaining_capacity_mwp": None,
        }

    row = case.iloc[0]

    return {
        "year30_remaining_capacity_percent": float(row["remaining_capacity_percent"]),
        "year30_aging_loss_percent": float(row["aging_loss_percent"]),
        "year30_remaining_pmax_wp": float(row["remaining_Pmax_Wp"]),
        "year30_plant_remaining_capacity_mwp": float(row["plant_remaining_capacity_MWp"]),
    }


def extract_bess_values(bess_df: pd.DataFrame) -> dict:
    """
    Extract BESS sizing results for 4MW-2h and 4MW-4h.
    """
    result = {}

    for scenario in ["4MW-2h", "4MW-4h"]:
        row_df = bess_df[bess_df["scenario"] == scenario]

        if row_df.empty:
            continue

        row = row_df.iloc[0]
        result[scenario] = {
            "required_units": int(row["required_units"]),
            "installed_power_mw": float(row["installed_power_mw"]),
            "installed_energy_mwh": float(row["installed_energy_mwh"]),
            "duration_at_target_power_h": float(row["duration_at_target_power_h"]),
            "design_note": row["design_note"],
        }

    return result


def build_task_completion_summary(
    kpi_values: dict,
    deg_values: dict,
    bess_values: dict,
) -> pd.DataFrame:
    """
    Build task completion summary table.
    """
    rows = [
        {
            "task": "PV operational loss analysis",
            "status": "Completed",
            "main_output": "outputs/processed/pv_loss_rule_engine_output.csv",
            "key_result": (
                f"Valid KPI rows = {kpi_values['valid_rows']}; "
                f"energy loss = {kpi_values['overall_energy_loss_percent']:.2f}%; "
                f"PR proxy = {kpi_values['overall_pr_proxy']:.3f}"
            ),
            "limitation": (
                "Short-term operational loss only; not direct PV aging/degradation."
            ),
        },
        {
            "task": "PV anomaly classification",
            "status": "Completed",
            "main_output": "outputs/metrics/pv_anomaly_summary.csv",
            "key_result": (
                "Anomaly flags include low irradiance, curtailment, "
                "baseline underestimation, suspected unrecorded constraint, "
                "and edge irradiance instability."
            ),
            "limitation": (
                "Anomaly flags suggest possible causes but do not prove root cause."
            ),
        },
        {
            "task": "LONGi datasheet-based degradation simulation",
            "status": "Completed",
            "main_output": "outputs/metrics/longi_degradation_summary.csv",
            "key_result": (
                f"540Wp case year 30: remaining capacity = "
                f"{deg_values['year30_remaining_capacity_percent']:.2f}%; "
                f"remaining Pmax = {deg_values['year30_remaining_pmax_wp']:.2f} Wp; "
                f"plant remaining capacity = "
                f"{deg_values['year30_plant_remaining_capacity_mwp']:.2f} MWp"
            ),
            "limitation": (
                "Datasheet/warranty simulation only; not measured field degradation."
            ),
        },
        {
            "task": "Sungrow BESS sizing",
            "status": "Completed",
            "main_output": "outputs/metrics/sungrow_bess_sizing_summary.csv",
            "key_result": (
                f"4MW-2h: {bess_values['4MW-2h']['required_units']} units, "
                f"{bess_values['4MW-2h']['installed_power_mw']:.2f} MW, "
                f"{bess_values['4MW-2h']['installed_energy_mwh']:.3f} MWh. "
                f"4MW-4h: {bess_values['4MW-4h']['required_units']} units, "
                f"{bess_values['4MW-4h']['installed_power_mw']:.2f} MW installed PCS, "
                f"{bess_values['4MW-4h']['installed_energy_mwh']:.3f} MWh."
            ),
            "limitation": (
                "Preliminary datasheet-based sizing; official SLD/vendor design is required."
            ),
        },
    ]

    return pd.DataFrame(rows)


def build_markdown_report(
    kpi_df: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    degradation_df: pd.DataFrame,
    bess_df: pd.DataFrame,
    task_summary_df: pd.DataFrame,
    kpi_values: dict,
    deg_values: dict,
    bess_values: dict,
) -> str:
    """
    Build supervisor-friendly Markdown report.
    """
    kpi_table = markdown_table(kpi_df)
    anomaly_table = markdown_table(anomaly_df)

    degradation_selected = degradation_df[
        (degradation_df["scenario"] == "540Wp")
        & (degradation_df["year"].isin([0, 1, 5, 10, 20, 30]))
    ][
        [
            "scenario",
            "year",
            "initial_Pmax_Wp",
            "remaining_capacity_percent",
            "aging_loss_percent",
            "remaining_Pmax_Wp",
            "plant_remaining_capacity_MWp",
        ]
    ]

    degradation_table = markdown_table(degradation_selected)
    bess_table = markdown_table(bess_df)
    task_table = markdown_table(task_summary_df)

    report = f"""# Supervisor Summary Report

## 1. Purpose

This report summarizes the current progress of the PV-BESS analysis task.  
The work separates short-term PV operational loss from long-term PV degradation.

The current outputs cover:

1. PV operational loss analysis from 30-minute cleaned data.
2. PV anomaly classification and KPI filtering.
3. LONGi datasheet-based PV degradation simulation.
4. Sungrow datasheet-based BESS sizing.

---

## 2. Main Result Overview

### 2.1 PV operational loss KPI

The KPI calculation uses only rows marked as `valid_for_kpi`.

Main result:

- Valid KPI rows: **{kpi_values['valid_rows']}**
- Expected energy: **{kpi_values['overall_expected_mwh']:.2f} MWh**
- Measured energy: **{kpi_values['overall_measured_mwh']:.2f} MWh**
- Energy loss: **{kpi_values['overall_energy_loss_percent']:.2f}%**
- PR proxy: **{kpi_values['overall_pr_proxy']:.3f}**

Important interpretation:

The value above represents short-term operational loss under the current baseline model.  
It should not be interpreted as measured PV module aging.

### KPI Summary

{kpi_table}

---

## 3. Anomaly Summary

The analysis keeps all data but adds anomaly flags to avoid incorrect conclusions.

Main anomaly types include:

- Low irradiance / nighttime.
- Curtailment recorded.
- Baseline underestimation.
- Suspected unrecorded curtailment or operational constraint.
- Edge irradiance instability.

{anomaly_table}

Important interpretation:

High loss is not automatically PV aging.  
It may be caused by curtailment, inverter limitation, sensor mismatch, timestamp mismatch, soiling, shading, or operational dispatch.

---

## 4. LONGi Datasheet-Based Degradation Simulation

The LONGi degradation model is based on datasheet/warranty assumptions:

- First-year degradation: 2%.
- Year 2 to Year 30 degradation: 0.45% per year.
- Simulation cases: 530Wp, 540Wp, 550Wp.

For the representative 540Wp case at year 30:

- Remaining capacity: **{deg_values['year30_remaining_capacity_percent']:.2f}%**
- Aging loss: **{deg_values['year30_aging_loss_percent']:.2f}%**
- Remaining Pmax: **{deg_values['year30_remaining_pmax_wp']:.2f} Wp**
- Plant remaining capacity: **{deg_values['year30_plant_remaining_capacity_mwp']:.2f} MWp**

### 540Wp Degradation Summary

{degradation_table}

Important interpretation:

This is a datasheet-based degradation simulation, not measured degradation from the two-month operational dataset.

---

## 5. Sungrow BESS Sizing

The Sungrow sizing uses the unit-level datasheet values:

- Unit energy: 229 kWh.
- Unit power: 110 kW.

### Main results

For 4MW-2h:

- Required units: **{bess_values['4MW-2h']['required_units']}**
- Installed power: **{bess_values['4MW-2h']['installed_power_mw']:.2f} MW**
- Installed energy: **{bess_values['4MW-2h']['installed_energy_mwh']:.3f} MWh**
- Duration at 4MW: **{bess_values['4MW-2h']['duration_at_target_power_h']:.2f} h**

For 4MW-4h:

- Required units: **{bess_values['4MW-4h']['required_units']}**
- Installed power: **{bess_values['4MW-4h']['installed_power_mw']:.2f} MW**
- Installed energy: **{bess_values['4MW-4h']['installed_energy_mwh']:.3f} MWh**
- Duration at 4MW: **{bess_values['4MW-4h']['duration_at_target_power_h']:.2f} h**

Important interpretation:

The 4MW-4h scenario satisfies the energy requirement, but the installed PCS power becomes higher than 4MW.  
Therefore, an export/control limit at 4MW or a vendor-provided 4h-specific configuration is required.

### BESS Sizing Table

{bess_table}

---

## 6. Task Completion Summary

{task_table}

---

## 7. Remaining Data Needed

To move from simulation and operational baseline analysis to confirmed field diagnosis, the following data is still required:

1. Official PV module BOM and exact module model.
2. Plant DC capacity and AC capacity confirmation.
3. Number of modules, string configuration, inverter/MPPT layout.
4. Multi-year PV operational data.
5. Cleaning and maintenance logs.
6. Curtailment, AGC, and dispatch records.
7. Inverter/string current and voltage data.
8. Soiling, shading, rainfall, and environmental data.
9. Thermal images, IV curve, or EL test for module-level degradation validation.
10. Official BESS SLD, vendor proposal, transformer/PCS grouping, and operation logs.

---

## 8. Final Conclusion

The current implementation completes the short-term PV operational loss analysis, anomaly classification, datasheet-based PV degradation simulation, and datasheet-based BESS sizing.

The PV operational loss KPI shows an energy loss of **{kpi_values['overall_energy_loss_percent']:.2f}%** and PR proxy of **{kpi_values['overall_pr_proxy']:.3f}** on valid KPI rows.  
However, this is not direct evidence of PV module aging.

The LONGi degradation model shows that a 540Wp module may retain **{deg_values['year30_remaining_capacity_percent']:.2f}%** capacity after 30 years under datasheet warranty assumptions.  
The Sungrow BESS sizing shows that 37 units satisfy 4MW-2h, while 70 units satisfy the energy requirement for 4MW-4h but require power/export control or a vendor-specific 4h configuration.
"""

    return report


def main() -> None:
    project_root = get_project_root()

    metrics_dir = project_root / "outputs" / "metrics"
    reports_dir = project_root / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    kpi_path = metrics_dir / "pv_loss_kpi_summary.csv"
    anomaly_path = metrics_dir / "pv_anomaly_summary.csv"
    degradation_path = metrics_dir / "longi_degradation_summary.csv"
    bess_path = metrics_dir / "sungrow_bess_sizing_summary.csv"

    kpi_df = read_csv_required(kpi_path)
    anomaly_df = read_csv_required(anomaly_path)
    degradation_df = read_csv_required(degradation_path)
    bess_df = read_csv_required(bess_path)

    kpi_values = extract_kpi_values(kpi_df)
    deg_values = extract_degradation_values(degradation_df)
    bess_values = extract_bess_values(bess_df)

    task_summary_df = build_task_completion_summary(
        kpi_values=kpi_values,
        deg_values=deg_values,
        bess_values=bess_values,
    )

    task_summary_path = metrics_dir / "task_completion_summary.csv"
    task_summary_df.to_csv(task_summary_path, index=False)

    report = build_markdown_report(
        kpi_df=kpi_df,
        anomaly_df=anomaly_df,
        degradation_df=degradation_df,
        bess_df=bess_df,
        task_summary_df=task_summary_df,
        kpi_values=kpi_values,
        deg_values=deg_values,
        bess_values=bess_values,
    )

    report_path = reports_dir / "supervisor_summary.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"Saved supervisor report: {report_path}")
    print(f"Saved task completion summary: {task_summary_path}")

    print("\nKey report summary:")
    print(f"PV valid KPI rows: {kpi_values['valid_rows']}")
    print(f"PV energy loss: {kpi_values['overall_energy_loss_percent']:.2f}%")
    print(f"PV PR proxy: {kpi_values['overall_pr_proxy']:.3f}")
    print(
        "LONGi 540Wp year 30: "
        f"{deg_values['year30_remaining_capacity_percent']:.2f}% remaining, "
        f"{deg_values['year30_remaining_pmax_wp']:.2f} Wp"
    )
    print(
        "Sungrow 4MW-2h: "
        f"{bess_values['4MW-2h']['required_units']} units, "
        f"{bess_values['4MW-2h']['installed_energy_mwh']:.3f} MWh"
    )
    print(
        "Sungrow 4MW-4h: "
        f"{bess_values['4MW-4h']['required_units']} units, "
        f"{bess_values['4MW-4h']['installed_energy_mwh']:.3f} MWh"
    )


if __name__ == "__main__":
    main()