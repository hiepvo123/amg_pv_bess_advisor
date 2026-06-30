import pandas as pd


REQUIRED_COLUMNS = [
    "date",
    "h0_m",
    "h24_m",
    "h_mean_m",
    "q_turbine_m3s",
    "q_inflow_m3s",
    "q_evap_m3s",
]


def clean_hydro_data(raw_df):
    """
    Clean and derive hydrology variables.

    English:
    This function guarantees that the output has a 'date' column.

    Vietnamese:
    Hàm này đảm bảo dữ liệu đầu ra có cột 'date' để vẽ EDA và model.
    """
    df = raw_df.copy()

    if "date" not in df.columns:
        raise ValueError(
            "Missing required column 'date'. Your loader did not parse the Excel files correctly. "
            f"Current columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    numeric_cols = [
        "h0_m",
        "h24_m",
        "delta_h_reported_m",
        "volume24_mcm",
        "q_turbine_m3s",
        "q_inflow_m3s",
        "q_spill_m3s",
        "q_evap_m3s",
        "q_minflow_m3s",
    ]

    for col in numeric_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # For May: h24 is missing. Infer h24(today) from h0(tomorrow) if available.
    df["h24_inferred_from_next_h0"] = False
    missing_h24 = df["h24_m"].isna()
    next_h0 = df["h0_m"].shift(-1)
    next_date = df["date"].shift(-1)
    is_next_day = (next_date - df["date"]).dt.days == 1

    infer_mask = missing_h24 & is_next_day & next_h0.notna()
    df.loc[infer_mask, "h24_m"] = next_h0[infer_mask]
    df.loc[infer_mask, "h24_inferred_from_next_h0"] = True

    # Mean reservoir level. This is a proxy; true hydropower head needs tailwater and loss.
    df["h_mean_m"] = df[["h0_m", "h24_m"]].mean(axis=1)

    # Daily water-level change.
    df["delta_h_calc_m"] = df["h24_m"] - df["h0_m"]
    df["delta_h_error_m"] = df["delta_h_reported_m"] - df["delta_h_calc_m"]

    # Outflow components.
    for col in ["q_turbine_m3s", "q_spill_m3s", "q_evap_m3s", "q_minflow_m3s"]:
        if col not in df.columns:
            df[col] = 0.0

    df["q_total_out_m3s"] = df[[
        "q_turbine_m3s",
        "q_spill_m3s",
        "q_evap_m3s",
        "q_minflow_m3s",
    ]].sum(axis=1, min_count=1)

    # Storage/water-balance check.
    df["volume_delta_mcm"] = df["volume24_mcm"].diff()
    df["q_storage_equiv_m3s"] = df["volume_delta_mcm"] * 1_000_000 / 86400
    df["water_balance_residual_m3s"] = df["q_storage_equiv_m3s"] - (
        df["q_inflow_m3s"] - df["q_total_out_m3s"]
    )

    return df
