"""
Data cleaning logic.
"""
import pandas as pd
import numpy as np
from core.common.constants import logger

def to_number(value) -> float:
    """
    Convert a value to float. Handle '-' and Vietnamese decimal commas.
    Returns np.nan if conversion fails or if value is missing/dash.
    """
    if pd.isna(value):
        return np.nan
    
    val_str = str(value).strip()
    if val_str == "-" or val_str == "":
        return np.nan
    
    # Handle Vietnamese decimal comma and typos like '26.,2' -> '26..2' -> '26.2'
    val_str = val_str.replace(",", ".")
    # Fix multiple dots
    while ".." in val_str:
        val_str = val_str.replace("..", ".")
    
    try:
        return float(val_str)
    except ValueError:
        return np.nan

def clean_operational_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the operational DataFrame.
    """
    df_clean = df.copy()
    
    # List of columns that should be numeric
    numeric_cols = [
        "wind_ms", "temp_air_c", "temp_pv_c", "irradiance_poa_wm2",
        "p_431_mw", "q_431_mvar", "p_calc_irr_mw", "p_meter_431_mw",
        "dhd_mw", "a0_mw", "selected_mw", "dev_dhd_pct", "dev_a0_pct",
        "p_setpoint_agc_mw", "p_curtail_mw"
    ]
    
    for col in numeric_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(to_number)
            
    df_clean = validate_daily_cycles(df_clean)
    df_clean = flag_outliers(df_clean)
    
    # Add daytime flag
    # B.xạ nghiêng is used as irradiance_poa_wm2
    if "irradiance_poa_wm2" in df_clean.columns:
        df_clean["is_daytime"] = df_clean["irradiance_poa_wm2"] > 20
    else:
        df_clean["is_daytime"] = False
        
    return df_clean

def validate_daily_cycles(df: pd.DataFrame) -> pd.DataFrame:
    """Validate cycles and apply basic rules without dropping rows."""
    df_clean = df.copy()
    
    if "irradiance_poa_wm2" in df_clean.columns:
        # Irradiance cannot be negative
        df_clean.loc[df_clean["irradiance_poa_wm2"] < 0, "irradiance_poa_wm2"] = 0.0
        
    if "wind_ms" in df_clean.columns:
        # Wind speed cannot be negative
        df_clean.loc[df_clean["wind_ms"] < 0, "wind_ms"] = 0.0
        
    return df_clean

def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Flag very abnormal values and replace them with the mean of the next two valid rows."""
    df_clean = df.copy()
    
    def get_mean_of_next_two(col_name, start_idx, threshold_func):
        pos = df_clean.index.get_loc(start_idx)
        next_vals = []
        # Search up to 5 next rows to find 2 valid ones
        for offset in range(1, 6):
            if pos + offset < len(df_clean):
                val = df_clean[col_name].iloc[pos + offset]
                if not pd.isna(val) and not threshold_func(val):
                    next_vals.append(val)
                    if len(next_vals) == 2:
                        break
        
        return np.mean(next_vals) if next_vals else np.nan

    if "temp_pv_c" in df_clean.columns:
        is_pv_outlier = lambda x: x > 100
        outlier_mask = df_clean["temp_pv_c"].apply(lambda x: pd.notna(x) and is_pv_outlier(x))
        n_outliers = outlier_mask.sum()
        if n_outliers > 0:
            logger.warning(f"Flagged {n_outliers} outliers in temp_pv_c (>100C). Setting to mean of next two rows.")
            for idx in df_clean[outlier_mask].index:
                df_clean.at[idx, "temp_pv_c"] = get_mean_of_next_two("temp_pv_c", idx, is_pv_outlier)
            
    if "temp_air_c" in df_clean.columns:
        is_air_outlier = lambda x: x > 60 or x < -10
        outlier_mask = df_clean["temp_air_c"].apply(lambda x: pd.notna(x) and is_air_outlier(x))
        n_outliers = outlier_mask.sum()
        if n_outliers > 0:
            logger.warning(f"Flagged {n_outliers} outliers in temp_air_c. Setting to mean of next two rows.")
            for idx in df_clean[outlier_mask].index:
                df_clean.at[idx, "temp_air_c"] = get_mean_of_next_two("temp_air_c", idx, is_air_outlier)

    return df_clean
