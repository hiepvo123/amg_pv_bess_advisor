def add_time_features(df):
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["day_of_year"] = df["date"].dt.dayofyear
    return df


def add_lag_features(df):
    df = df.copy()
    if "q_turbine_m3s" in df.columns:
        df["q_turbine_lag1"] = df["q_turbine_m3s"].shift(1)
    if "h_mean_m" in df.columns:
        df["h_mean_lag1"] = df["h_mean_m"].shift(1)
    return df


def add_rolling_features(df):
    df = df.copy()
    if "q_turbine_m3s" in df.columns:
        df["q_turbine_rolling3"] = df["q_turbine_m3s"].rolling(3).mean()
    if "h_mean_m" in df.columns:
        df["h_mean_rolling3"] = df["h_mean_m"].rolling(3).mean()
    return df
