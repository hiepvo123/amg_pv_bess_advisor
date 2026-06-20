"""
Metrics functions for model evaluation.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def regression_metrics(y_true, y_pred) -> dict:
    """Calculate standard regression metrics."""
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "R2": r2_score(y_true, y_pred),
    }

def evaluate_all_day_and_daytime(df: pd.DataFrame, target_col: str, pred_col: str) -> pd.DataFrame:
    """Evaluate metrics for all data and explicitly for daytime."""
    df_eval = df.dropna(subset=[target_col, pred_col])
    if len(df_eval) == 0:
        return pd.DataFrame()
        
    all_metrics = regression_metrics(df_eval[target_col], df_eval[pred_col])
    
    if "is_daytime" in df_eval.columns:
        day_df = df_eval[df_eval["is_daytime"] == True]
        if len(day_df) > 0:
            day_metrics = regression_metrics(day_df[target_col], day_df[pred_col])
        else:
            day_metrics = {"MAE": np.nan, "RMSE": np.nan, "R2": np.nan}
    else:
        day_metrics = {"MAE": np.nan, "RMSE": np.nan, "R2": np.nan}
        
    results = [
        {"Subset": "All", **all_metrics},
        {"Subset": "Daytime", **day_metrics}
    ]
    return pd.DataFrame(results)

def daily_error_report(df: pd.DataFrame, target_col: str, pred_col: str, power_interval_hours: float = 0.5) -> pd.DataFrame:
    """
    Calculate daily energy error (MWh).
    Requires a dataframe with 'date', target_col, and pred_col.
    """
    df_eval = df.dropna(subset=[target_col, pred_col]).copy()
    if len(df_eval) == 0 or "date" not in df_eval.columns:
        return pd.DataFrame()
        
    # Calculate energy per step
    df_eval["actual_energy_mwh"] = df_eval[target_col] * power_interval_hours
    df_eval["pred_energy_mwh"] = df_eval[pred_col] * power_interval_hours
    
    # Aggregate daily
    daily = df_eval.groupby("date").agg(
        actual_energy_mwh=("actual_energy_mwh", "sum"),
        pred_energy_mwh=("pred_energy_mwh", "sum"),
        mae=("actual_energy_mwh", lambda x: mean_absolute_error(x, df_eval.loc[x.index, "pred_energy_mwh"]))
    ).reset_index()
    
    daily["error_mwh"] = daily["pred_energy_mwh"] - daily["actual_energy_mwh"]
    daily["error_pct"] = (daily["error_mwh"] / daily["actual_energy_mwh"].replace(0, np.nan)) * 100
    
    return daily
