"""
Feature engineering logic.
"""
import pandas as pd
import numpy as np

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add cyclical time features."""
    df_feat = df.copy()
    
    # Calculate float hour, e.g., 6:30 is 6.5
    df_feat["hour_float"] = df_feat["hour"] + df_feat["minute"] / 60.0
    
    # Cyclical hour features (24 hours)
    df_feat["hour_sin"] = np.sin(2 * np.pi * df_feat["hour_float"] / 24.0)
    df_feat["hour_cos"] = np.cos(2 * np.pi * df_feat["hour_float"] / 24.0)
    
    # Cyclical day of year features (365/366 days)
    # Using 365.25 for average year length
    df_feat["doy_sin"] = np.sin(2 * np.pi * df_feat["day_of_year"] / 365.25)
    df_feat["doy_cos"] = np.cos(2 * np.pi * df_feat["day_of_year"] / 365.25)
    
    return df_feat

def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag features across the entire dataset consecutively."""
    df_feat = df.copy()
    
    # Sort by datetime to ensure chronological order before shifting
    df_feat = df_feat.sort_values("datetime")
    
    if "irradiance_poa_wm2" in df_feat.columns:
        df_feat["irradiance_poa_wm2_lag1"] = df_feat["irradiance_poa_wm2"].shift(1)
        df_feat["irradiance_poa_wm2_lag2"] = df_feat["irradiance_poa_wm2"].shift(2)
        
    if "temp_air_c" in df_feat.columns:
        df_feat["temp_air_c_lag1"] = df_feat["temp_air_c"].shift(1)
        
    if "temp_pv_c" in df_feat.columns:
        df_feat["temp_pv_c_lag1"] = df_feat["temp_pv_c"].shift(1)
        
    if "wind_ms" in df_feat.columns:
        df_feat["wind_ms_lag1"] = df_feat["wind_ms"].shift(1)
        
    if "p_meter_431_mw" in df_feat.columns:
        df_feat["p_meter_431_mw_lag1"] = df_feat["p_meter_431_mw"].shift(1)
        
    return df_feat

def make_irradiance_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Prepare dataset for Task 1: Irradiance forecasting.
    Target: Next step POA irradiance.
    """
    df_task = df.copy()
    
    # Sort by datetime just to be safe
    df_task = df_task.sort_values("datetime")
    
    # Create target variable: next step irradiance consecutively across the whole dataset
    df_task["irradiance_poa_next_wm2"] = df_task["irradiance_poa_wm2"].shift(-1)
    
    target_col = "irradiance_poa_next_wm2"
    
    features = [
        "hour_sin", "hour_cos", "doy_sin", "doy_cos",
        "irradiance_poa_wm2_lag1", "irradiance_poa_wm2_lag2",
        "temp_air_c_lag1", "temp_pv_c_lag1", "wind_ms_lag1"
    ]
    
    # Add optional features if they exist and aren't entirely empty
    if "p_meter_431_mw_lag1" in df_task.columns and not df_task["p_meter_431_mw_lag1"].isna().all():
        features.append("p_meter_431_mw_lag1")
        
    # Drop rows where target is missing
    df_task = df_task.dropna(subset=[target_col])
    
    return df_task, target_col, features

def make_power_dataset(df: pd.DataFrame, include_tilt: bool = False, tilt_angle_deg: float | None = None) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Prepare dataset for Task 2: PV Power prediction.
    """
    df_task = df.copy()
    
    # Determine target column
    if "p_meter_431_mw" in df_task.columns and df_task["p_meter_431_mw"].count() > len(df_task) * 0.1:
        target_col = "p_meter_431_mw"
    elif "p_431_mw" in df_task.columns:
        target_col = "p_431_mw"
    else:
        raise ValueError("Neither p_meter_431_mw nor p_431_mw found in dataset for power target.")
        
    features = [
        "irradiance_poa_wm2",
        "temp_air_c",
        "temp_pv_c",
        "wind_ms",
        "hour_sin",
        "hour_cos",
        "doy_sin",
        "doy_cos",
    ]
    
    if include_tilt and tilt_angle_deg is not None:
        df_task["tilt_angle_deg"] = tilt_angle_deg
        features.append("tilt_angle_deg")
        
    # Ensure all required columns exist
    features = [f for f in features if f in df_task.columns]
    
    df_task = df_task.dropna(subset=[target_col])
    
    return df_task, target_col, features
