import pytest
import pandas as pd
import numpy as np
from core.data_section.data_cleaning import to_number, validate_daily_cycles, flag_outliers

def test_to_number():
    assert to_number("12.5") == 12.5
    assert to_number("12,5") == 12.5
    assert np.isnan(to_number("-"))
    assert np.isnan(to_number(""))
    assert np.isnan(to_number(None))

def test_validate_daily_cycles():
    df = pd.DataFrame({
        "irradiance_poa_wm2": [-10, 50, 100],
        "wind_ms": [-5, 10, 0]
    })
    cleaned = validate_daily_cycles(df)
    assert cleaned["irradiance_poa_wm2"][0] == 0.0
    assert cleaned["wind_ms"][0] == 0.0

def test_flag_outliers():
    df = pd.DataFrame({
        "temp_pv_c": [25, 40, 150],
        "temp_air_c": [20, -20, 30]
    })
    flagged = flag_outliers(df)
    assert np.isnan(flagged["temp_pv_c"][2])
    assert np.isnan(flagged["temp_air_c"][1])
    assert flagged["temp_pv_c"][0] == 25
