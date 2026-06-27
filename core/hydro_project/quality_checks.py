import pandas as pd


def _build_qc_flags(row):
    flags = []

    if pd.isna(row.get("h0_m")):
        flags.append("missing_h0")
    if pd.isna(row.get("h24_m")):
        flags.append("missing_h24")
    if pd.isna(row.get("q_turbine_m3s")):
        flags.append("missing_q_turbine")
    if pd.isna(row.get("q_inflow_m3s")):
        flags.append("missing_q_inflow")
    if pd.isna(row.get("q_evap_m3s")):
        flags.append("missing_evap")

    if pd.notna(row.get("delta_h_error_m")) and abs(row["delta_h_error_m"]) > 1e-6:
        flags.append("delta_report_calc_mismatch")

    if pd.notna(row.get("delta_h_calc_m")) and abs(row["delta_h_calc_m"]) > 0.6:
        flags.append("large_daily_water_level_change_check")

    for col in ["q_turbine_m3s", "q_inflow_m3s", "q_spill_m3s", "q_evap_m3s", "q_minflow_m3s"]:
        value = row.get(col)
        if pd.notna(value) and value < 0:
            flags.append(f"negative_{col}")

    if pd.notna(row.get("water_balance_residual_m3s")) and abs(row["water_balance_residual_m3s"]) > 5:
        flags.append("water_balance_residual_check")

    return ";".join(flags) if flags else "OK"


def run_quality_checks(df):
    """
    Add row-level QC flags and return the checked dataframe.
    """
    qc_df = df.copy()
    qc_df["qc_flags"] = qc_df.apply(_build_qc_flags, axis=1)
    return qc_df


def make_qc_summary(df):
    """
    Produce missing/count/min/mean/max summary for numeric columns.
    """
    rows = []
    numeric_cols = df.select_dtypes(include="number").columns

    for col in numeric_cols:
        rows.append({
            "variable": col,
            "count": int(df[col].count()),
            "missing": int(df[col].isna().sum()),
            "min": df[col].min(skipna=True),
            "mean": df[col].mean(skipna=True),
            "max": df[col].max(skipna=True),
        })

    return pd.DataFrame(rows)
