"""
Constants and common configurations for the pipeline.
"""
import logging

# Define fixed electricity price
ELECTRICITY_PRICE_VND_PER_KWH = 3460.0

# Expected column names extracted from operational tables
EXPECTED_COLUMNS = [
    "cycle",
    "time_range",
    "wind_ms",
    "temp_air_c",
    "temp_pv_c",
    "irradiance_poa_wm2",
    "p_431_mw",
    "q_431_mvar",
    "p_calc_irr_mw",
    "p_meter_431_mw",
    "dhd_mw",
    "a0_mw",
    "selected_mw",
    "dev_dhd_pct",
    "dev_a0_pct",
    "p_setpoint_agc_mw",
    "p_curtail_mw",
    "evaluation",
]

def setup_logging(level=logging.INFO) -> logging.Logger:
    """Setup structured logging for the pipeline."""
    logger = logging.getLogger("pv_advisor")
    if not logger.handlers:
        logger.setLevel(level)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

# Get default logger instance
logger = setup_logging()
