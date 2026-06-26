"""
core/pv_model.py

PV power simulation model - AMG PV-BESS Advisor (v1).
Role: PV Model Owner.

Deterministic physics formula (v1 does not require AI/ML forecasting):

    P(t) = pv_capacity * G(t)/G_ref * [1 + gamma * (T(t) - T_ref)] * loss_factor

    G(t)        : irradiance on the panel surface (GHI/POA), W/m^2
    T(t)        : panel or ambient temperature, deg C
    gamma       : temperature coefficient of power (temp_coeff), 1/degC
                  (decimal, NOT percent)
    loss_factor : system derate factor (wiring, soiling, mismatch...), (0, 1]
    G_ref, T_ref: STC reference conditions - default 1000 W/m^2, 25 degC

Default test values (see tests/test_pv_model.py):
    - pv_capacity = 47.5 MW - actual installed capacity of the DHD plant
      (known project fact, no external datasheet needed).
    - temp_coeff = -0.00410 (-0.41 %/degC) - from the confirmed panel model:
      LONGi Solar LR6-72HV-340M (datasheet source: provided to team by AMG).
      Note: if the old DHD plant uses a different panel and no datasheet is
      available, use -0.0034 (-0.34 %/degC) as a temporary assumption and
      document it clearly (per teacher's guidance).
"""
from pathlib import Path
from typing import Union, Sequence

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.common.constants import logger

ArrayLike = Union[float, int, Sequence[float], np.ndarray, pd.Series]

# STC (Standard Test Conditions) reference values
STC_GHI_WM2 = 1000.0
STC_TEMP_C = 25.0


def _to_array(x: ArrayLike) -> np.ndarray:
    """Coerce scalar/list/Series into a 1-D+ float64 array (always indexable)."""
    return np.atleast_1d(np.asarray(x, dtype=np.float64))


def calculate_pv_power(
    ghi: ArrayLike,
    temperature: ArrayLike,
    pv_capacity: float,
    temp_coeff: float,
    loss_factor: float = 1.0,
    *,
    ref_ghi_wm2: float = STC_GHI_WM2,
    ref_temp_c: float = STC_TEMP_C,
) -> np.ndarray:
    """
    Compute PV output power from irradiance and temperature.

    Parameters:
    ghi : array-like
        Irradiance on the panel surface, W/m^2. Scalar, list, numpy array,
        or pandas Series. Negative values (sensor noise) are clipped to 0.
    temperature : array-like
        Panel or ambient temperature, deg C. Same length as `ghi` (or a
        scalar to broadcast).
    pv_capacity : float
        Rated capacity at STC. Any unit (kW, MW...) - output is in the
        same unit.
    temp_coeff : float
        Temperature coefficient of power (gamma), 1/degC decimal. Typical
        crystalline silicon panel: -0.003 to -0.0045.
        Confirmed model LONGi Solar LR6-72HV-340M: -0.00410 (-0.41 %/degC).
    loss_factor : float, default 1.0
        System derate factor, (0, 1].
    ref_ghi_wm2 : float, default 1000.0
        STC reference irradiance, W/m^2.
    ref_temp_c : float, default 25.0
        STC reference temperature, deg C.

    Returns
    -------
    np.ndarray
        PV power, same unit as pv_capacity, same length as `ghi`.
        Always >= 0 (GHI=0 must give P=0 regardless of temperature).

    Raises
    ------
    ValueError
        If pv_capacity <= 0, loss_factor not in (0, 1], or ghi/temperature
        lengths mismatch and cannot broadcast.

    Examples
    --------
    >>> calculate_pv_power(ghi=0, temperature=25, pv_capacity=47.5,
    ...                     temp_coeff=-0.00410, loss_factor=0.95)
    array([0.])

    >>> # At STC with no system loss, output must equal rated capacity
    >>> calculate_pv_power(ghi=1000, temperature=25, pv_capacity=47.5,
    ...                     temp_coeff=-0.00410, loss_factor=1.0)
    array([47.5])
    """
    if pv_capacity <= 0:
        raise ValueError(f"pv_capacity must be > 0, got {pv_capacity}")
    if not (0.0 < loss_factor <= 1.0):
        raise ValueError(f"loss_factor must be in (0, 1], got {loss_factor}")

    ghi_arr = _to_array(ghi)
    temp_arr = _to_array(temperature)

    if ghi_arr.shape != temp_arr.shape:
        try:
            ghi_arr, temp_arr = np.broadcast_arrays(ghi_arr, temp_arr)
        except ValueError as exc:
            raise ValueError(
                f"ghi (len={ghi_arr.size}) and temperature (len={temp_arr.size}) "
                "must match length or be broadcastable"
            ) from exc

    # Negative irradiance (sensor noise) clipped to 0 - no such thing as negative light
    ghi_clipped = np.clip(ghi_arr, 0.0, None)

    temp_factor = 1.0 + temp_coeff * (temp_arr - ref_temp_c)
    power = pv_capacity * (ghi_clipped / ref_ghi_wm2) * temp_factor * loss_factor

    # Power can never go negative even if temp_factor < 0 at extreme temperatures
    power = np.clip(power, 0.0, None)

    return power


def calculate_pv_energy(power: ArrayLike, interval_minutes: float = 30.0) -> float:
    """
    Integrate a PV power time series into total energy.

    Parameters:
    power : array-like
        Power time series (same unit as calculate_pv_power output, e.g. MW),
        assumed evenly sampled.
    interval_minutes : float, default 30.0
        Sampling interval, minutes. DHD operational reports use 30-min cycles.

    Returns
    -------
    float
        Total energy (e.g. MWh if power is in MW).
    """
    power_arr = _to_array(power)
    dt_hours = interval_minutes / 60.0
    return float(np.sum(power_arr) * dt_hours)


def get_pv_power_table(
    df: pd.DataFrame,
    pv_capacity: float,
    temp_coeff: float,
    loss_factor: float = 1.0,
    ghi_col: str = "irradiance_poa_wm2",
    temp_col: str = "temp_pv_c",
) -> pd.DataFrame:
    """
    Apply calculate_pv_power() to a DataFrame and return a result table.

    Default column names match the cleaned schema produced by
    core/data_section (outputs/processed/pv_30min_clean.csv).

    Parameters:
    df : pd.DataFrame
        Must contain `ghi_col` and `temp_col`. `datetime` column (if present)
        is preserved in the output.
    pv_capacity, temp_coeff, loss_factor :
        See calculate_pv_power().
    ghi_col : str, default "irradiance_poa_wm2"
        Irradiance column name in `df`.
    temp_col : str, default "temp_pv_c"
        Temperature column name in `df`.

    Returns
    -------
    pd.DataFrame
        Relevant columns plus a new `pv_power_calc` column.
    """
    missing = [c for c in (ghi_col, temp_col) if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s) in df: {missing}")

    result = df.copy()
    result["pv_power_calc"] = calculate_pv_power(
        ghi=result[ghi_col],
        temperature=result[temp_col],
        pv_capacity=pv_capacity,
        temp_coeff=temp_coeff,
        loss_factor=loss_factor,
    )
    keep_cols = [c for c in ["datetime", "date", ghi_col, temp_col] if c in result.columns]
    keep_cols.append("pv_power_calc")
    return result[keep_cols]


def plot_pv_power_profile(
    df: pd.DataFrame,
    output_path: Path,
    power_col: str = "pv_power_calc",
    time_col: str = "datetime",
) -> None:
    """
    Plot the PV power time series and save to a file.

    Matplotlib style consistent with the rest of the project
    (core/data_section/eda.py): figsize (10, 5), tight_layout.
    """
    if power_col not in df.columns or time_col not in df.columns:
        logger.warning(
            f"plot_pv_power_profile: missing '{power_col}' or '{time_col}' - skipped"
        )
        return

    # Parse real datetime - otherwise every row becomes its own x-axis label
    # and thousands of rows make the axis unreadable.
    time_values = pd.to_datetime(df[time_col])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(time_values, df[power_col], color="#F2A33C", linewidth=1)
    ax.set_title("Simulated PV Power Profile")
    ax.set_xlabel("Time")
    ax.set_ylabel(f"Power ({power_col})")

    # Cap the number of x-axis ticks (~12) regardless of series length
    locator = mdates.AutoDateLocator(maxticks=12)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.autofmt_xdate(rotation=45)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved PV power profile chart to {output_path}")


# PV surplus/deficit vs load 

def calculate_pv_surplus(pv_power: ArrayLike, load: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute PV surplus and deficit relative to load.

    Required PV module output per spec section 8 ("PV power surplus vs
    load"). Consumed downstream by the Rule Engine (dispatch_rule.py) to
    decide BESS charge/discharge, but computed here as the PV module's
    responsibility.

    Parameters:
    pv_power : array-like
        PV power (output of calculate_pv_power), same unit as load.
    load : array-like
        Load power, same unit and length as pv_power.

    Returns
    -------
    (surplus, deficit) : tuple[np.ndarray, np.ndarray]
        surplus : PV - load, clipped to 0 - used for BESS charge rule.
        deficit : load - PV, clipped to 0 - used for BESS discharge rule.

    Raises
    ------
    ValueError
        If pv_power and load lengths mismatch and cannot broadcast.
    """
    pv_arr = _to_array(pv_power)
    load_arr = _to_array(load)

    if pv_arr.shape != load_arr.shape:
        try:
            pv_arr, load_arr = np.broadcast_arrays(pv_arr, load_arr)
        except ValueError as exc:
            raise ValueError(
                f"pv_power (len={pv_arr.size}) and load (len={load_arr.size}) "
                "must match length or be broadcastable"
            ) from exc

    diff = pv_arr - load_arr
    surplus = np.clip(diff, 0.0, None)
    deficit = np.clip(-diff, 0.0, None)
    return surplus, deficit


# PV energy table by day/month/year 

_FREQ_LABELS = {"D": "day", "M": "month", "Y": "year"}
# pandas >= 2.2 renamed resample aliases 'M' -> 'ME' and 'Y' -> 'YE';
# map the simple public API ("D"/"M"/"Y") to whatever pandas expects.
_PANDAS_FREQ_MAP = {"D": "D", "M": "ME", "Y": "YE"}


def get_pv_energy_table(
    df: pd.DataFrame,
    power_col: str = "pv_power_calc",
    time_col: str = "datetime",
    freq: str = "D",
    interval_minutes: float = 30.0,
) -> pd.DataFrame:
    """
    Aggregate a PV power series into an energy table by time period.

    Required PV module output per spec section 15 ("PV energy table").

    Parameters:
    df : pd.DataFrame
        PV power table, e.g. output of get_pv_power_table(). Must have
        `power_col` and `time_col`.
    power_col : str, default "pv_power_calc"
        PV power column name.
    time_col : str, default "datetime"
        Time column name (datetime or parseable string).
    freq : {"D", "M", "Y"}, default "D"
        Aggregation period: day, month, or year.
    interval_minutes : float, default 30.0
        Sampling interval between power readings, minutes.

    Returns
    -------
    pd.DataFrame
        2 columns: `period` and `pv_energy` (energy, e.g. MWh).

    Raises
    ------
    ValueError
        If a required column is missing or `freq` is invalid.
    """
    if freq not in _FREQ_LABELS:
        raise ValueError(f"freq must be one of {list(_FREQ_LABELS)}, got {freq!r}")
    missing = [c for c in (power_col, time_col) if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s) in df: {missing}")

    work = df[[time_col, power_col]].copy()
    work[time_col] = pd.to_datetime(work[time_col])
    dt_hours = interval_minutes / 60.0

    grouped = (
        work.set_index(time_col)
        .resample(_PANDAS_FREQ_MAP[freq])[power_col]
        .apply(lambda s: float(np.sum(s.to_numpy()) * dt_hours))
        .reset_index()
        .rename(columns={time_col: "period", power_col: "pv_energy"})
    )
    return grouped


def plot_pv_energy_by_period(
    energy_df: pd.DataFrame,
    output_path: Path,
    freq: str = "D",
    period_col: str = "period",
    energy_col: str = "pv_energy",
) -> None:
    """
    Plot a PV energy bar chart by day/month/year and save to a file.

    Call once per freq ("D", "M", "Y") to cover all three views required
    by spec section 8.
    """
    if period_col not in energy_df.columns or energy_col not in energy_df.columns:
        logger.warning(
            f"plot_pv_energy_by_period: missing '{period_col}' or '{energy_col}' - skipped"
        )
        return

    label = _FREQ_LABELS.get(freq, freq)
    period_labels = energy_df[period_col].astype(str)
    n = len(period_labels)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(period_labels, energy_df[energy_col], color="#F2A33C")
    ax.set_title(f"PV Energy Production by {label.capitalize()}")
    ax.set_xlabel(label.capitalize())
    ax.set_ylabel("Energy (e.g. MWh)")

    # Cap displayed x-axis labels (~15) for long series (e.g. 365 days)
    max_labels = 15
    if n > max_labels:
        step = -(-n // max_labels)  # ceiling division
        shown_ticks = list(range(0, n, step))
        ax.set_xticks(shown_ticks)
        ax.set_xticklabels([period_labels.iloc[i] for i in shown_ticks])

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Saved PV energy-by-{label} chart to {output_path}")