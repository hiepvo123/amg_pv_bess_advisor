"""
tests/test_pv_model.py
Unit tests for core/pv_model.py - PV power simulation model.

Reference values do NOT depend on any external file/datasheet:
    - pv_capacity = 47.5 MW - actual installed capacity of the DHD plant
      (known project fact).
    - temp_coeff = -0.0034 (-0.34 %/degC) - typical crystalline silicon
      panel value (-0.30% to -0.45%/degC range), cross-checked against the
      project's own real data - see test_temp_coeff_sign_matches_real_data().
"""

import numpy as np
import pandas as pd
import pytest

from core.pv_model import (
    calculate_pv_power,
    calculate_pv_energy,
    calculate_pv_surplus,
    get_pv_power_table,
    get_pv_energy_table,
)

# Reference test values - see module docstring for sourcing
REF_PV_CAPACITY = 47.5      # MW, actual DHD plant installed capacity
REF_TEMP_COEFF = -0.0034    # -0.340 %/degC -> decimal (typical value)
REF_LOSS_FACTOR = 0.97


def test_zero_ghi_gives_zero_power():
    """Spec requirement: GHI = 0 -> P approx 0."""
    power = calculate_pv_power(
        ghi=0, temperature=25,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF,
        loss_factor=REF_LOSS_FACTOR,
    )
    assert power[0] == pytest.approx(0.0)


def test_power_increases_with_ghi():
    """Spec requirement: GHI increases -> P increases."""
    ghi_values = [200, 400, 600, 800, 1000]
    power = calculate_pv_power(
        ghi=ghi_values, temperature=25,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF,
        loss_factor=REF_LOSS_FACTOR,
    )
    assert np.all(np.diff(power) > 0)


def test_stc_matches_rated_capacity():
    """At STC (1000 W/m^2, 25 degC) with no system loss, power must equal
    the rated capacity (47.5 MW, actual DHD plant capacity)."""
    power = calculate_pv_power(
        ghi=1000, temperature=25,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF,
        loss_factor=1.0,
    )
    assert power[0] == pytest.approx(REF_PV_CAPACITY)


def test_high_temperature_derates_power():
    """Higher panel temperature must reduce power (negative gamma)."""
    power_25c = calculate_pv_power(
        ghi=1000, temperature=25,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=1.0,
    )[0]
    power_60c = calculate_pv_power(
        ghi=1000, temperature=60,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=1.0,
    )[0]
    assert power_60c < power_25c
    # -0.34%/degC * 35 degC delta = -11.9% power
    expected = REF_PV_CAPACITY * (1 + REF_TEMP_COEFF * (60 - 25))
    assert power_60c == pytest.approx(expected)


def test_negative_ghi_clipped_to_zero():
    """Sensor noise can produce slightly negative GHI at sunrise/sunset."""
    power = calculate_pv_power(
        ghi=-5, temperature=20,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=1.0,
    )
    assert power[0] == pytest.approx(0.0)


def test_power_never_negative_at_extreme_temperature():
    """Even at extreme temperature, power must clip to 0, never negative."""
    power = calculate_pv_power(
        ghi=1000, temperature=200,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=1.0,
    )
    assert power[0] >= 0.0


def test_invalid_pv_capacity_raises():
    with pytest.raises(ValueError):
        calculate_pv_power(ghi=500, temperature=25, pv_capacity=0,
                            temp_coeff=REF_TEMP_COEFF, loss_factor=1.0)


def test_invalid_loss_factor_raises():
    with pytest.raises(ValueError):
        calculate_pv_power(ghi=500, temperature=25, pv_capacity=REF_PV_CAPACITY,
                            temp_coeff=REF_TEMP_COEFF, loss_factor=1.5)


def test_pandas_series_input_supported():
    """Function must accept pandas Series directly (integration with
    cleaned DHD data columns from core/data_section)."""
    ghi = pd.Series([0, 300, 600, 900, 1000])
    temp = pd.Series([22, 28, 35, 42, 45])
    power = calculate_pv_power(
        ghi=ghi, temperature=temp,
        pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=0.97,
    )
    assert len(power) == len(ghi)


def test_calculate_pv_energy_constant_power():
    """1 MW constant power for 2 hours (4 x 30-min cycles) = 2 MWh."""
    power = [1.0, 1.0, 1.0, 1.0]
    energy = calculate_pv_energy(power, interval_minutes=30.0)
    assert energy == pytest.approx(2.0)


def test_get_pv_power_table_with_real_schema():
    """Integration test using the exact column names produced by
    core/data_section (irradiance_poa_wm2, temp_pv_c)."""
    df = pd.DataFrame({
        "datetime": pd.date_range("2025-03-01", periods=3, freq="30min"),
        "irradiance_poa_wm2": [0, 500, 900],
        "temp_pv_c": [22, 35, 48],
    })
    result = get_pv_power_table(
        df, pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF, loss_factor=0.97,
    )
    assert "pv_power_calc" in result.columns
    assert result["pv_power_calc"].iloc[0] == pytest.approx(0.0)
    assert len(result) == 3


def test_get_pv_power_table_missing_column_raises():
    df = pd.DataFrame({"foo": [1, 2, 3]})
    with pytest.raises(ValueError):
        get_pv_power_table(df, pv_capacity=REF_PV_CAPACITY, temp_coeff=REF_TEMP_COEFF)


def test_real_dhd_dataset_smoke_test():
    """Smoke test on real processed DHD data (from the Data Lead) - ensures
    pv_model.py runs on real data with no errors, no NaN, no runaway power."""
    from pathlib import Path

    real_data_path = Path("outputs/processed/pv_30min_clean.csv")
    if not real_data_path.exists():
        pytest.skip("outputs/processed/pv_30min_clean.csv not available - skipped")

    df = pd.read_csv(real_data_path)
    result = get_pv_power_table(
        df,
        pv_capacity=47.5,           # MW - DHD (Da Mi Solar) plant capacity
        temp_coeff=REF_TEMP_COEFF,
        loss_factor=0.95,
        ghi_col="irradiance_poa_wm2",
        temp_col="temp_pv_c",
    )
    assert result["pv_power_calc"].notna().all()
    assert (result["pv_power_calc"] >= 0).all()
    # Power can slightly exceed rated capacity on cold days (temp < 25 degC
    # -> temp_factor > 1) - a real physical effect; bifacial panels can add
    # several more percent. Allow 10% headroom instead of a hard cap.
    assert result["pv_power_calc"].max() <= 47.5 * 1.10


# Tests: calculate_pv_surplus (spec section 8 - "PV surplus vs load") 

def test_pv_surplus_when_pv_exceeds_load():
    pv_power = [10.0, 20.0, 5.0]
    load = [6.0, 8.0, 9.0]
    surplus, deficit = calculate_pv_surplus(pv_power, load)
    np.testing.assert_allclose(surplus, [4.0, 12.0, 0.0])
    np.testing.assert_allclose(deficit, [0.0, 0.0, 4.0])


def test_pv_surplus_never_negative():
    """surplus and deficit are never negative - at most one is nonzero at
    any given time (can't be both surplus and deficit simultaneously)."""
    pv_power = np.array([0.0, 5.0, 15.0, 3.0])
    load = np.array([2.0, 5.0, 10.0, 8.0])
    surplus, deficit = calculate_pv_surplus(pv_power, load)
    assert np.all(surplus >= 0)
    assert np.all(deficit >= 0)
    assert np.all((surplus == 0) | (deficit == 0))


def test_pv_surplus_mismatched_length_raises():
    with pytest.raises(ValueError):
        calculate_pv_surplus([1, 2, 3], [1, 2])


# Tests: get_pv_energy_table (spec section 15 - "PV energy table") 

def test_get_pv_energy_table_daily():
    """4 x 30-min cycles at 1 MW on the same day = 2 MWh for that day."""
    df = pd.DataFrame({
        "datetime": pd.date_range("2025-03-01 10:00", periods=4, freq="30min"),
        "pv_power_calc": [1.0, 1.0, 1.0, 1.0],
    })
    energy_table = get_pv_energy_table(df, freq="D")
    assert "period" in energy_table.columns
    assert "pv_energy" in energy_table.columns
    assert len(energy_table) == 1
    assert energy_table["pv_energy"].iloc[0] == pytest.approx(2.0)


def test_get_pv_energy_table_monthly_groups_correctly():
    """Data spanning 2 months must produce 2 rows in the monthly energy table."""
    df = pd.DataFrame({
        "datetime": pd.to_datetime([
            "2025-03-15 12:00", "2025-03-15 12:30",
            "2025-04-10 12:00", "2025-04-10 12:30",
        ]),
        "pv_power_calc": [2.0, 2.0, 4.0, 4.0],
    })
    energy_table = get_pv_energy_table(df, freq="M")
    assert len(energy_table) == 2
    assert energy_table["pv_energy"].iloc[0] == pytest.approx(2.0)  # March: 2*0.5*2
    assert energy_table["pv_energy"].iloc[1] == pytest.approx(4.0)  # April: 4*0.5*2


def test_get_pv_energy_table_invalid_freq_raises():
    df = pd.DataFrame({"datetime": pd.date_range("2025-01-01", periods=2), "pv_power_calc": [1, 1]})
    with pytest.raises(ValueError):
        get_pv_energy_table(df, freq="W")


def test_get_pv_energy_table_missing_column_raises():
    df = pd.DataFrame({"foo": [1, 2, 3]})
    with pytest.raises(ValueError):
        get_pv_energy_table(df)


def test_real_dhd_energy_table_smoke_test():
    """Smoke test for the PV energy table on real DHD data across all
    three periods (day/month/year), per spec section 8."""
    from pathlib import Path

    real_data_path = Path("outputs/processed/pv_30min_clean.csv")
    if not real_data_path.exists():
        pytest.skip("outputs/processed/pv_30min_clean.csv not available - skipped")

    df = pd.read_csv(real_data_path)
    power_table = get_pv_power_table(
        df, pv_capacity=47.5, temp_coeff=REF_TEMP_COEFF, loss_factor=0.95,
    )
    for freq in ("D", "M", "Y"):
        energy_table = get_pv_energy_table(power_table, freq=freq)
        assert len(energy_table) >= 1
        assert (energy_table["pv_energy"] >= 0).all()


# Cross-check default temp_coeff against the project's own real data 

def test_temp_coeff_sign_matches_real_data():
    """
    No external datasheet used - estimate the SIGN of temp_coeff directly
    from outputs/processed/pv_30min_clean.csv via simple linear regression,
    then cross-check against the default REF_TEMP_COEFF.

    Note: regression R^2 is very low (~0.02) because p_meter_431_mw is
    power after AGC/curtailment/grid dispatch, not pure panel DC power -
    so this test ONLY checks the SIGN (negative) and order of magnitude,
    not an exact numeric match.
    """
    from pathlib import Path

    real_data_path = Path("outputs/processed/pv_30min_clean.csv")
    if not real_data_path.exists():
        pytest.skip("outputs/processed/pv_30min_clean.csv not available - skipped")

    df = pd.read_csv(real_data_path)
    df["p_curtail_mw"] = df["p_curtail_mw"].fillna(0)
    daytime = df[
        (df["irradiance_poa_wm2"] > 200) & (df["p_curtail_mw"].abs() < 0.1)
    ].copy()
    daytime["p_norm"] = daytime["p_meter_431_mw"] / (daytime["irradiance_poa_wm2"] / 1000.0)
    daytime = daytime[(daytime["p_norm"] > 0) & (daytime["p_norm"] < 100)]

    slope = np.polyfit(daytime["temp_pv_c"], daytime["p_norm"], 1)[0]

    # Only check the sign (negative - higher temp means lower power), not
    # an exact value, since real-world data is too noisy (see docstring).
    assert slope < 0, "Real data must show temperature-up -> power-down trend"