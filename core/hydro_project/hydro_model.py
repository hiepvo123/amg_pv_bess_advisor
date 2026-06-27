from config import RHO_WATER, GRAVITY, DEFAULT_EFFICIENCY, DEFAULT_TAILWATER_LEVEL, DEFAULT_HYDRAULIC_LOSS


def calculate_net_head(reservoir_level, tailwater_level, hydraulic_loss):
    """
    H_net = H_reservoir - H_tailwater - H_loss
    """
    return reservoir_level - tailwater_level - hydraulic_loss


def calculate_power_mw(q_m3s, h_net_m, efficiency):
    """
    P = rho * g * Q * H * eta / 1e6
    """
    return (RHO_WATER * GRAVITY * q_m3s * h_net_m * efficiency) / 1_000_000


def calculate_hydropower(
    df,
    tailwater_level=DEFAULT_TAILWATER_LEVEL,
    hydraulic_loss=DEFAULT_HYDRAULIC_LOSS,
    efficiency=DEFAULT_EFFICIENCY,
):
    model_df = df.copy()

    if "h_mean_m" not in model_df.columns or "q_turbine_m3s" not in model_df.columns:
        raise ValueError("Need h_mean_m and q_turbine_m3s before calculating hydropower.")

    model_df["net_head_m"] = calculate_net_head(
        model_df["h_mean_m"],
        tailwater_level,
        hydraulic_loss,
    )

    # Do not calculate where Q is missing.
    model_df["p_theoretical_mw"] = calculate_power_mw(
        model_df["q_turbine_m3s"],
        model_df["net_head_m"],
        efficiency,
    )

    model_df["e_daily_mwh"] = model_df["p_theoretical_mw"] * 24

    return model_df
