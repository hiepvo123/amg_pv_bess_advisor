import math
import pandas as pd


def to_float(value):
    """Safely convert Excel values like '0.57' or '0,57' to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    text = str(value).strip().replace(",", ".")
    if text == "":
        return None

    try:
        return float(text)
    except ValueError:
        return None


def is_date_like(value):
    """Return True if a cell value can be interpreted as a date."""
    return pd.to_datetime(value, errors="coerce") is not pd.NaT


def normalize_date(value):
    """Convert Excel datetime / pandas timestamp / string to date."""
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()
