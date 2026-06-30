"""
PV Loss Analysis Module

Purpose:
- Read cleaned 30-minute PV operational data.
- Compute expected PV power using irradiance and PV temperature.
- Compare expected power with measured power.
- Calculate power loss, loss percentage, temperature loss, and PR proxy.
- Export rule-engine-ready outputs and daily/monthly summaries.

Important limitation:
- This module estimates short-term operational loss.
- It does NOT prove real long-term PV aging/degradation.
- Real degradation rate requires multi-year data, official plant design,
  cleaning/maintenance logs, string-level data, and module inspection data.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from core.pv_model import calculate_pv_power


def build_measured_power_series(df: pd.DataFrame) -> pd.Series:
    """
    Build measured PV power series.

    Priority:
    1. Use p_meter_431_mw where available.
    2. If p_meter_431_mw is NaN, fallback to p_431_mw.

    Why:
    - p_meter_431_mw has 48 missing rows in the current dataset.
    - p_431_mw has no missing values and can fill those gaps.
    """
    if "p_meter_431_mw" not in df.columns and "p_431_mw" not in df.columns:
        raise ValueError("Missing both p_meter_431_mw and p_431_mw.")

    if "p_meter_431_mw" in df.columns and "p_431_mw" in df.columns:
        return df["p_meter_431_mw"].fillna(df["p_431_mw"])

    if "p_meter_431_mw" in df.columns:
        return df["p_meter_431_mw"]

    return df["p_431_mw"]


def add_pv_loss_features(
    df: pd.DataFrame,
    pv_capacity_mw: float = 47.5,
    temp_coeff: float = -0.00340,
    loss_factor: float = 0.95,
    irradiance_col: str = "irradiance_poa_wm2",
    temp_col: str = "temp_pv_c",
) -> pd.DataFrame:
    """
    Add PV loss features.

    Parameters
    ----------
    df:
        Cleaned PV dataset.

    pv_capacity_mw:
        Rated PV plant capacity in MW.
        Current repo uses 47.5 MW as DHD plant capacity.

    temp_coeff:
        PV power temperature coefficient in 1/°C.
        LONGi Hi-MO 5 LR5-72HBD datasheet: -0.340%/°C = -0.00340/°C.

    loss_factor:
        General derating factor for system losses.
        0.95 means assumed 5% general system loss.

    irradiance_col:
        Plane-of-array irradiance column, W/m².

    temp_col:
        PV/module temperature column, °C.

    Returns
    -------
    DataFrame with:
    - P_expected_mw
    - P_measured_mw
    - power_loss_mw
    - power_loss_percent
    - temperature_loss_percent
    - PR_proxy
    """
    result = df.copy()

    if irradiance_col not in result.columns:
        raise ValueError(f"Missing required irradiance column: {irradiance_col}")

    if temp_col not in result.columns or result[temp_col].isna().all():
        if "temp_air_c" in result.columns:
            temp_col = "temp_air_c"
        else:
            raise ValueError("Missing temperature column: temp_pv_c or temp_air_c")

    result["P_measured_mw"] = build_measured_power_series(result)

    result["P_expected_mw"] = calculate_pv_power(
        ghi=result[irradiance_col],
        temperature=result[temp_col],
        pv_capacity=pv_capacity_mw,
        temp_coeff=temp_coeff,
        loss_factor=loss_factor,
    )

    valid_expected = result["P_expected_mw"] > 0

    result["power_loss_mw"] = np.where(
        valid_expected,
        result["P_expected_mw"] - result["P_measured_mw"],
        np.nan,
    )

    result["power_loss_percent"] = np.where(
        valid_expected,
        result["power_loss_mw"] / result["P_expected_mw"] * 100.0,
        np.nan,
    )

    # Avoid unrealistic values caused by noise or edge cases.
    result["power_loss_percent"] = result["power_loss_percent"].clip(
        lower=-100.0,
        upper=100.0,
    )

    # Temperature loss compared with STC 25°C.
    # Since temp_coeff is negative, high temperature produces positive loss.
    temp_diff = result[temp_col] - 25.0
    result["temperature_loss_percent"] = np.maximum(
        0.0,
        -temp_coeff * temp_diff * 100.0,
    )

    # PR proxy = measured power / expected power.
    # This is a short-term operational indicator, not a certified PR.
    result["PR_proxy"] = np.where(
        valid_expected,
        result["P_measured_mw"] / result["P_expected_mw"],
        np.nan,
    )

    result["PR_proxy"] = result["PR_proxy"].clip(lower=0.0, upper=2.0)

    result["temperature_source_col"] = temp_col
    result["temp_coeff_used"] = temp_coeff
    result["loss_factor_used"] = loss_factor
    result["pv_capacity_mw_used"] = pv_capacity_mw

    return result


def apply_basic_rule_engine(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply simple rule engine.

    Rule logic:
    - Low irradiance: do not evaluate PV loss.
    - High temperature: warning.
    - Loss > 10%: warning.
    - Loss > 20%: critical.
    - Curtailment > 0: curtailment explanation.
    """
    result = df.copy()

    result["warning_status"] = "Normal"
    result["recommended_action"] = "No action"

    low_irradiance = result["irradiance_poa_wm2"] < 100

    result.loc[low_irradiance, "warning_status"] = "Not evaluated"
    result.loc[
        low_irradiance,
        "recommended_action",
    ] = "Low irradiance or nighttime - do not evaluate PV loss"

    if "temp_pv_c" in result.columns:
        high_temp = (result["temp_pv_c"] >= 60) & (~low_irradiance)
        result.loc[high_temp, "warning_status"] = "Warning"
        result.loc[
            high_temp,
            "recommended_action",
        ] = "High PV module temperature - check temperature loss"

    high_loss = (result["power_loss_percent"] > 10) & (~low_irradiance)
    result.loc[high_loss, "warning_status"] = "Warning"
    result.loc[
        high_loss,
        "recommended_action",
    ] = "PV power below expected >10% - check soiling, shading, inverter or string"

    critical_loss = (result["power_loss_percent"] > 20) & (~low_irradiance)
    result.loc[critical_loss, "warning_status"] = "Critical"
    result.loc[
        critical_loss,
        "recommended_action",
    ] = "PV power below expected >20% - inspect inverter/string, soiling, shading or curtailment"

    if "p_curtail_mw" in result.columns:
        curtailment = (result["p_curtail_mw"].fillna(0.0) > 0.0) & (~low_irradiance)
        result.loc[curtailment, "warning_status"] = "Curtailment"
        result.loc[
            curtailment,
            "recommended_action",
        ] = "PV reduction may be caused by curtailment or dispatch limit"

    return result
def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add data-quality and anomaly flags for safer reporting.

    New columns:
    - valid_for_kpi:
        True if the row is stable enough for KPI calculation.
    - anomaly_flag:
        Short label describing the anomaly type.
    - suspicious_reason:
        Human-readable explanation.

    Why this is needed:
    - Low irradiance periods can produce unstable loss percentages.
    - PR_proxy > 1.10 means measured power is higher than expected,
      so the physical baseline may underestimate actual production.
    - Large loss without curtailment record should not be interpreted
      directly as PV aging.
    """
    result = df.copy()

    irradiance = result["irradiance_poa_wm2"]
    expected = result["P_expected_mw"]
    pr = result["PR_proxy"]
    loss_pct = result["power_loss_percent"]

    if "p_curtail_mw" in result.columns:
        curtailment = result["p_curtail_mw"].fillna(0.0) > 0.0
    else:
        curtailment = pd.Series(False, index=result.index)

    low_irradiance = irradiance < 100
    edge_irradiance = (irradiance >= 100) & (irradiance < 300)
    stable_irradiance = irradiance >= 300

    result["valid_for_kpi"] = (
        stable_irradiance
        & (expected >= 5.0)
        & pr.notna()
        & (~curtailment)
    )

    result["anomaly_flag"] = "none"
    result["suspicious_reason"] = ""

    # 1. Low irradiance / nighttime
    mask = low_irradiance
    result.loc[mask, "anomaly_flag"] = "low_irradiance_not_evaluated"
    result.loc[
        mask,
        "suspicious_reason",
    ] = "Low irradiance or nighttime; PV loss percentage is not evaluated."

    # 2. Edge irradiance unstable zone
    mask = edge_irradiance & (loss_pct.abs() > 40)
    result.loc[mask, "anomaly_flag"] = "edge_irradiance_unstable"
    result.loc[
        mask,
        "suspicious_reason",
    ] = (
        "Irradiance is between 100 and 300 W/m²; loss percentage may be unstable "
        "because it is morning/evening or low-sun condition."
    )

    # 3. Baseline underestimation: measured much higher than expected
    mask = stable_irradiance & (~curtailment) & (pr > 1.10)
    result.loc[mask, "anomaly_flag"] = "baseline_underestimation"
    result.loc[
        mask,
        "suspicious_reason",
    ] = (
        "Measured power is much higher than expected; check irradiance sensor, "
        "timestamp alignment, bifacial gain, or baseline calibration."
    )

    # 4. Large loss without curtailment record
    mask = stable_irradiance & (~curtailment) & (loss_pct > 40)
    result.loc[mask, "anomaly_flag"] = "suspected_unrecorded_constraint"
    result.loc[
        mask,
        "suspicious_reason",
    ] = (
        "Large loss without curtailment record; possible unrecorded dispatch limit, "
        "inverter limitation, soiling/shading, or sensor mismatch."
    )

    # 5. Recorded curtailment should override other flags
    mask = curtailment & (irradiance >= 100)
    result.loc[mask, "anomaly_flag"] = "curtailment_recorded"
    result.loc[
        mask,
        "suspicious_reason",
    ] = (
        "Curtailment value is recorded; power reduction is likely caused by "
        "dispatch/curtailment rather than PV module aging."
    )

    return result

def make_kpi_summary(df: pd.DataFrame, interval_minutes: float = 30.0) -> pd.DataFrame:
    """
    Create KPI summary using only rows marked as valid_for_kpi.

    This avoids using low-irradiance or curtailment rows as official KPI data.
    """
    result = df.copy()
    result["datetime"] = pd.to_datetime(result["datetime"])
    result["month"] = result["datetime"].dt.to_period("M").astype(str)

    dt_h = interval_minutes / 60.0

    kpi = result[result["valid_for_kpi"]].copy()

    rows = []

    def summarize(scope_name: str, data: pd.DataFrame) -> None:
        if data.empty:
            rows.append({
                "scope": scope_name,
                "rows": 0,
                "energy_expected_mwh": np.nan,
                "energy_measured_mwh": np.nan,
                "energy_loss_mwh": np.nan,
                "energy_loss_percent": np.nan,
                "avg_loss_percent": np.nan,
                "median_loss_percent": np.nan,
                "avg_pr_proxy": np.nan,
                "warning_count": 0,
                "critical_count": 0,
            })
            return

        energy_expected = data["P_expected_mw"].sum() * dt_h
        energy_measured = data["P_measured_mw"].sum() * dt_h
        energy_loss = energy_expected - energy_measured

        rows.append({
            "scope": scope_name,
            "rows": len(data),
            "energy_expected_mwh": energy_expected,
            "energy_measured_mwh": energy_measured,
            "energy_loss_mwh": energy_loss,
            "energy_loss_percent": (
                energy_loss / energy_expected * 100.0
                if energy_expected > 0
                else np.nan
            ),
            "avg_loss_percent": data["power_loss_percent"].mean(),
            "median_loss_percent": data["power_loss_percent"].median(),
            "avg_pr_proxy": data["PR_proxy"].mean(),
            "warning_count": (data["warning_status"] == "Warning").sum(),
            "critical_count": (data["warning_status"] == "Critical").sum(),
        })

    summarize("overall_valid_kpi", kpi)

    for month, group in kpi.groupby("month"):
        summarize(f"month_{month}", group)

    return pd.DataFrame(rows)

def make_anomaly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize anomaly flags.
    """
    result = df.copy()
    result["datetime"] = pd.to_datetime(result["datetime"])

    summary = result.groupby("anomaly_flag").agg(
        count=("anomaly_flag", "size"),
        first_datetime=("datetime", "min"),
        last_datetime=("datetime", "max"),
        avg_irradiance_wm2=("irradiance_poa_wm2", "mean"),
        avg_loss_percent=("power_loss_percent", "mean"),
        avg_pr_proxy=("PR_proxy", "mean"),
    ).reset_index()

    return summary.sort_values("count", ascending=False)

def make_daily_summary(df: pd.DataFrame, interval_minutes: float = 30.0) -> pd.DataFrame:
    """
    Summarize PV loss by day.
    """
    result = df.copy()
    result["datetime"] = pd.to_datetime(result["datetime"])
    result["date"] = result["datetime"].dt.date

    dt_h = interval_minutes / 60.0
    daytime = result[result["irradiance_poa_wm2"] >= 100].copy()

    daily = daytime.groupby("date").agg(
        energy_expected_mwh=("P_expected_mw", lambda x: x.sum() * dt_h),
        energy_measured_mwh=("P_measured_mw", lambda x: x.sum() * dt_h),
        avg_loss_percent=("power_loss_percent", "mean"),
        median_loss_percent=("power_loss_percent", "median"),
        avg_temperature_loss_percent=("temperature_loss_percent", "mean"),
        avg_pr_proxy=("PR_proxy", "mean"),
        max_temp_pv_c=("temp_pv_c", "max"),
        max_irradiance_wm2=("irradiance_poa_wm2", "max"),
        warning_count=("warning_status", lambda x: (x != "Normal").sum()),
        critical_count=("warning_status", lambda x: (x == "Critical").sum()),
        curtailment_count=("warning_status", lambda x: (x == "Curtailment").sum()),
    ).reset_index()

    daily["energy_loss_mwh"] = (
        daily["energy_expected_mwh"] - daily["energy_measured_mwh"]
    )

    daily["energy_loss_percent"] = np.where(
        daily["energy_expected_mwh"] > 0,
        daily["energy_loss_mwh"] / daily["energy_expected_mwh"] * 100.0,
        np.nan,
    )

    return daily


def make_monthly_summary(df: pd.DataFrame, interval_minutes: float = 30.0) -> pd.DataFrame:
    """
    Summarize PV loss by month.
    """
    result = df.copy()
    result["datetime"] = pd.to_datetime(result["datetime"])
    result["month"] = result["datetime"].dt.to_period("M").astype(str)

    dt_h = interval_minutes / 60.0
    daytime = result[result["irradiance_poa_wm2"] >= 100].copy()

    monthly = daytime.groupby("month").agg(
        energy_expected_mwh=("P_expected_mw", lambda x: x.sum() * dt_h),
        energy_measured_mwh=("P_measured_mw", lambda x: x.sum() * dt_h),
        avg_loss_percent=("power_loss_percent", "mean"),
        median_loss_percent=("power_loss_percent", "median"),
        avg_temperature_loss_percent=("temperature_loss_percent", "mean"),
        avg_pr_proxy=("PR_proxy", "mean"),
        warning_count=("warning_status", lambda x: (x != "Normal").sum()),
        critical_count=("warning_status", lambda x: (x == "Critical").sum()),
        curtailment_count=("warning_status", lambda x: (x == "Curtailment").sum()),
    ).reset_index()

    monthly["energy_loss_mwh"] = (
        monthly["energy_expected_mwh"] - monthly["energy_measured_mwh"]
    )

    monthly["energy_loss_percent"] = np.where(
        monthly["energy_expected_mwh"] > 0,
        monthly["energy_loss_mwh"] / monthly["energy_expected_mwh"] * 100.0,
        np.nan,
    )

    return monthly


def run_pv_loss_analysis(
    input_csv: str = r"C:\Users\DuNhan\PycharmProjects\amg_pv_bess_advisor\outputs\processed\pv_30min_clean.csv",
    output_dir: str = r"C:\Users\DuNhan\PycharmProjects\amg_pv_bess_advisor\outputs",
    pv_capacity_mw: float = 47.5,
    temp_coeff: float = -0.00340,
    loss_factor: float = 0.95,
    interval_minutes: float = 30.0,
) -> None:
    """
    Run full PV loss analysis.
    """
    output_dir = Path(output_dir)
    processed_dir = output_dir / "processed"
    metrics_dir = output_dir / "metrics"

    processed_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_csv)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. "
            "Run core.run_pipeline first to generate pv_30min_clean.csv."
        )

    df = pd.read_csv(input_path)

    if "datetime" not in df.columns:
        raise ValueError("Input data must contain datetime column.")

    df["datetime"] = pd.to_datetime(df["datetime"])

    loss_df = add_pv_loss_features(
        df=df,
        pv_capacity_mw=pv_capacity_mw,
        temp_coeff=temp_coeff,
        loss_factor=loss_factor,
    )

    loss_df = apply_basic_rule_engine(loss_df)
    loss_df = add_quality_flags(loss_df)

    keep_cols = [
        "datetime",
        "date",
        "irradiance_poa_wm2",
        "temp_air_c",
        "temp_pv_c",
        "wind_ms",
        "P_expected_mw",
        "P_measured_mw",
        "power_loss_mw",
        "power_loss_percent",
        "temperature_loss_percent",
        "PR_proxy",
        "p_curtail_mw",
        "warning_status",
        "recommended_action",
        "temperature_source_col",
        "temp_coeff_used",
        "loss_factor_used",
        "pv_capacity_mw_used",
        "valid_for_kpi",
        "anomaly_flag",
        "suspicious_reason",
    ]

    keep_cols = [col for col in keep_cols if col in loss_df.columns]

    rule_engine_output_path = processed_dir / "pv_loss_rule_engine_output.csv"
    daily_summary_path = metrics_dir / "pv_loss_daily_summary.csv"
    monthly_summary_path = metrics_dir / "pv_pr_monthly_summary.csv"
    kpi_summary_path = metrics_dir / "pv_loss_kpi_summary.csv"
    anomaly_summary_path = metrics_dir / "pv_anomaly_summary.csv"

    loss_df[keep_cols].to_csv(rule_engine_output_path, index=False)

    daily_summary = make_daily_summary(
        loss_df,
        interval_minutes=interval_minutes,
    )
    daily_summary.to_csv(daily_summary_path, index=False)

    monthly_summary = make_monthly_summary(
        loss_df,
        interval_minutes=interval_minutes,
    )
    monthly_summary.to_csv(monthly_summary_path, index=False)

    kpi_summary = make_kpi_summary(
        loss_df,
        interval_minutes=interval_minutes,
    )
    kpi_summary.to_csv(kpi_summary_path, index=False)

    anomaly_summary = make_anomaly_summary(loss_df)
    anomaly_summary.to_csv(anomaly_summary_path, index=False)

    print("PV loss analysis completed.")
    print(f"Saved rule engine output: {rule_engine_output_path}")
    print(f"Saved daily summary: {daily_summary_path}")
    print(f"Saved monthly summary: {monthly_summary_path}")

    print(f"Saved KPI summary: {kpi_summary_path}")
    print(f"Saved anomaly summary: {anomaly_summary_path}")

    print("\nQuick summary:")
    print(f"Rows processed: {len(loss_df)}")
    print(f"Average loss percent: {loss_df['power_loss_percent'].mean():.2f}%")
    print(f"Average PR proxy: {loss_df['PR_proxy'].mean():.3f}")

    print("\nWarning status counts:")
    print(loss_df["warning_status"].value_counts(dropna=False))

    print("\nAnomaly flag counts:")
    print(loss_df["anomaly_flag"].value_counts(dropna=False))

    print("\nValid for KPI counts:")
    print(loss_df["valid_for_kpi"].value_counts(dropna=False))

if __name__ == "__main__":
    run_pv_loss_analysis()