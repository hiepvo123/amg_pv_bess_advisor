import pytest
import pandas as pd
import numpy as np
from core.data_section.feature_engineering import add_time_features, add_lag_features

def test_add_time_features():
    df = pd.DataFrame({
        "hour": [6, 12, 18],
        "minute": [30, 0, 0],
        "day_of_year": [1, 100, 200]
    })
    feat_df = add_time_features(df)
    assert "hour_float" in feat_df.columns
    assert feat_df["hour_float"][0] == 6.5
    assert "hour_sin" in feat_df.columns
    assert "hour_cos" in feat_df.columns
    assert "doy_sin" in feat_df.columns
    assert "doy_cos" in feat_df.columns

def test_add_lag_features():
    df = pd.DataFrame({
        "date": [pd.Timestamp("2025-03-01"), pd.Timestamp("2025-03-01"), pd.Timestamp("2025-03-02")],
        "irradiance_poa_wm2": [100, 200, 300]
    })
    lag_df = add_lag_features(df)
    # The first row of 03-01 should have NaN lag
    assert np.isnan(lag_df["irradiance_poa_wm2_lag1"][0])
    # The second row of 03-01 should have 100 as lag
    assert lag_df["irradiance_poa_wm2_lag1"][1] == 100
    # The first row of 03-02 should have NaN lag because of grouping by date
    assert np.isnan(lag_df["irradiance_poa_wm2_lag1"][2])
