"""
BESS Model — mô phỏng trạng thái pin theo chuỗi thời gian.

Mỗi bước thời gian dt (giờ):
  Nạp : ΔE_stored = P_ac × η_charge × dt
  Xả  : ΔE_ac     = P_stored / η_discharge × dt   →  ΔSoC = ΔE_ac / capacity

SoH suy giảm theo chu kỳ (rain-flow simplified):
  Mỗi chu kỳ đầy: SoH -= 20 / cycle_life
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from core.common.config import BESSConfig
from core.common.constants import logger


@dataclass
class BESSModelParams:
    capacity_kwh:   float = 8_000.0  # kWh (4 MW × 2h)
    pcs_power_kw:   float = 4_000.0  # kW — giới hạn PCS
    soc_min:        float = 10.0     # %
    soc_max:        float = 95.0     # %
    charge_eff:     float = 0.95
    discharge_eff:  float = 0.95
    initial_soc:    float = 50.0     # %
    cycle_life:     int   = 4_000    # số chu kỳ đến SoH = 80%
    dt_h:           float = 0.5      # bước thời gian (giờ) — 30 phút

    @classmethod
    def from_config(cls, cfg: BESSConfig) -> "BESSModelParams":
        params = cls()
        if cfg.bess_capacity_mwh is not None:
            params.capacity_kwh = cfg.bess_capacity_mwh * 1000
        if cfg.pcs_power_mw is not None:
            params.pcs_power_kw = cfg.pcs_power_mw * 1000
        if cfg.soc_min is not None:
            params.soc_min = cfg.soc_min
        if cfg.soc_max is not None:
            params.soc_max = cfg.soc_max
        if cfg.eta_ch is not None:
            params.charge_eff = cfg.eta_ch
        if cfg.eta_dis is not None:
            params.discharge_eff = cfg.eta_dis
        return params

    @property
    def usable_kwh(self) -> float:
        return self.capacity_kwh * (self.soc_max - self.soc_min) / 100.0


def simulate_bess_series(
    bess_cmd_series: pd.Series,
    bess_power_series: pd.Series,
    params: BESSModelParams,
) -> pd.DataFrame:
    """
    Mô phỏng BESS qua từng bước thời gian.

    Args:
        bess_cmd_series  : Series[str] — lệnh mỗi bước ('CHARGE'|'DISCHARGE'|'IDLE')
        bess_power_series: Series[float] — công suất yêu cầu AC (kW, dương)
        params           : BESSModelParams

    Returns:
        DataFrame gồm:
          bess_cmd, bess_power_ac_kw, soc, soh, energy_in_kwh, energy_out_kwh
    """
    n        = len(bess_cmd_series)
    soc      = np.full(n + 1, np.nan)
    soh_arr  = np.full(n + 1, np.nan)
    e_in     = np.zeros(n)
    e_out    = np.zeros(n)
    pwr_ac   = np.zeros(n)

    soc[0]     = params.initial_soc
    soh_arr[0] = 100.0
    partial    = 0.0   # partial cycle counter

    cap = params.capacity_kwh

    for i, (cmd, req_kw) in enumerate(zip(bess_cmd_series, bess_power_series)):
        cur_soc = soc[i]
        cur_soh = soh_arr[i]
        avail_cap = cap * (cur_soh / 100.0)
        req_kw = min(abs(req_kw), params.pcs_power_kw)

        if cmd == "CHARGE" and cur_soc < params.soc_max:
            # Năng lượng thực vào pin (kWh)
            e_stored = req_kw * params.charge_eff * params.dt_h
            dsoc     = (e_stored / avail_cap) * 100.0
            new_soc  = min(params.soc_max, cur_soc + dsoc)
            actual_dsoc = new_soc - cur_soc
            # Công suất AC thực (ngược từ dsoc thực)
            actual_e = (actual_dsoc / 100.0) * avail_cap
            act_kw   = actual_e / (params.charge_eff * params.dt_h)
            e_in[i]  = actual_e
            pwr_ac[i]= act_kw
            partial  += actual_dsoc / 100.0

        elif cmd == "DISCHARGE" and cur_soc > params.soc_min:
            # Năng lượng lấy từ pin (kWh)
            e_drawn  = req_kw / params.discharge_eff * params.dt_h
            dsoc     = (e_drawn / avail_cap) * 100.0
            new_soc  = max(params.soc_min, cur_soc - dsoc)
            actual_dsoc = cur_soc - new_soc
            actual_e = (actual_dsoc / 100.0) * avail_cap
            act_kw   = actual_e * params.discharge_eff / params.dt_h
            e_out[i] = actual_e
            pwr_ac[i]= -act_kw
            partial  += actual_dsoc / 100.0
        else:
            new_soc  = cur_soc
            pwr_ac[i]= 0.0

        soc[i + 1] = new_soc

        # Cập nhật SoH
        full_cycles = int(partial)
        if full_cycles > 0:
            soh_drop     = full_cycles * (20.0 / params.cycle_life)
            cur_soh      = max(0.0, cur_soh - soh_drop)
            partial     -= full_cycles
        soh_arr[i + 1] = cur_soh

    idx = bess_cmd_series.index
    result = pd.DataFrame({
        "bess_cmd":        bess_cmd_series.values,
        "bess_power_ac_kw": pwr_ac,
        "soc":             soc[:-1],
        "soc_end":         soc[1:],
        "soh":             soh_arr[:-1],
        "energy_in_kwh":   e_in,
        "energy_out_kwh":  e_out,
    }, index=idx)

    logger.info(
        f"BESS simulation: {n} steps, "
        f"total charged={e_in.sum():.1f} kWh, "
        f"total discharged={e_out.sum():.1f} kWh, "
        f"final SoC={soc[-1]:.1f}%, SoH={soh_arr[-1]:.2f}%"
    )
    return result


def bess_energy_summary(bess_df: pd.DataFrame) -> dict:
    """Tóm tắt năng lượng BESS từ kết quả mô phỏng."""
    total_in   = bess_df["energy_in_kwh"].sum()
    total_out  = bess_df["energy_out_kwh"].sum()
    rte        = (total_out / total_in) if total_in > 0 else 0.0
    cycles     = total_in / bess_df.attrs.get("usable_kwh", total_in or 1)
    return {
        "total_charged_kwh":    round(total_in, 1),
        "total_discharged_kwh": round(total_out, 1),
        "round_trip_eff":       round(rte, 4),
        "estimated_cycles":     round(cycles, 1),
        "final_soc":            round(bess_df["soc_end"].iloc[-1], 1),
        "final_soh":            round(bess_df["soh"].iloc[-1], 2),
    }
