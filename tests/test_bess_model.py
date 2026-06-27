"""Tests cho core/bess_model.py"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bess_model import BESSModelParams, simulate_bess_series, bess_energy_summary


def _run(cmds, powers=None, cap=100.0, pcs=50.0, soc0=50.0,
         eta_ch=0.95, eta_dis=0.95, soc_min=10.0, soc_max=95.0):
    idx  = pd.RangeIndex(len(cmds))
    c    = pd.Series(cmds, index=idx)
    p    = pd.Series(powers or [pcs] * len(cmds), index=idx)
    prm  = BESSModelParams(
        capacity_kwh=cap, pcs_power_kw=pcs,
        charge_eff=eta_ch, discharge_eff=eta_dis,
        initial_soc=soc0, soc_min=soc_min, soc_max=soc_max,
        dt_h=0.5,
    )
    return simulate_bess_series(c, p, prm), prm


class TestBESSModelParams:
    def test_defaults(self):
        p = BESSModelParams()
        assert p.capacity_kwh == 8_000.0
        assert p.pcs_power_kw == 4_000.0
        assert p.charge_eff   == 0.95

    def test_from_config(self):
        from core.common.config import BESSConfig
        cfg = BESSConfig(bess_capacity_mwh=10.0, pcs_power_mw=5.0,
                         eta_ch=0.93, eta_dis=0.93)
        p   = BESSModelParams.from_config(cfg)
        assert p.capacity_kwh == 10_000.0
        assert p.pcs_power_kw == 5_000.0
        assert p.charge_eff   == 0.93


class TestSimulateBESSSeries:
    def test_output_columns(self):
        df, _ = _run(["IDLE"] * 4)
        for col in ["bess_cmd", "bess_power_ac_kw", "soc", "soc_end", "soh",
                    "energy_in_kwh", "energy_out_kwh"]:
            assert col in df.columns

    def test_idle_does_not_change_soc(self):
        df, _ = _run(["IDLE"] * 10, soc0=60.0)
        assert (df["soc"] == 60.0).all()
        assert (df["energy_in_kwh"] == 0.0).all()

    def test_charging_increases_soc(self):
        df, _ = _run(["CHARGE"] * 6, powers=[20.0] * 6, soc0=50.0)
        assert df["soc_end"].iloc[-1] > 50.0

    def test_discharging_decreases_soc(self):
        df, _ = _run(["DISCHARGE"] * 6, powers=[20.0] * 6, soc0=70.0)
        assert df["soc_end"].iloc[-1] < 70.0

    def test_soc_never_exceeds_max(self):
        df, _ = _run(["CHARGE"] * 100, powers=[50.0] * 100, soc0=10.0, soc_max=95.0)
        assert (df["soc_end"] <= 95.0 + 1e-6).all()

    def test_soc_never_below_min(self):
        df, _ = _run(["DISCHARGE"] * 100, powers=[50.0] * 100, soc0=90.0, soc_min=10.0)
        assert (df["soc_end"] >= 10.0 - 1e-6).all()

    def test_charge_efficiency_loss(self):
        """Năng lượng đầu vào AC > năng lượng thực sự lưu (do tổn hao nạp)."""
        df, prm = _run(["CHARGE"] * 4, powers=[10.0] * 4, soc0=20.0, eta_ch=0.90, cap=1000.0)
        e_in_ac = df["bess_power_ac_kw"].abs().sum() * prm.dt_h
        e_stored = df["energy_in_kwh"].sum()
        assert e_in_ac > e_stored  # AC energy > stored energy

    def test_discharge_efficiency_loss(self):
        """Năng lượng lấy từ pin > năng lượng nhận được phía AC."""
        df, prm = _run(["DISCHARGE"] * 4, powers=[10.0] * 4, soc0=80.0, eta_dis=0.90, cap=1000.0)
        e_out_kwh = df["energy_out_kwh"].sum()   # năng lượng lấy từ pin
        e_ac_kwh  = df["bess_power_ac_kw"].abs().sum() * prm.dt_h
        assert e_out_kwh > e_ac_kwh

    def test_pcs_clamp(self):
        """Công suất yêu cầu vượt PCS bị clamp xuống pcs_power_kw."""
        df, prm = _run(["CHARGE"] * 4, powers=[9999.0] * 4, soc0=20.0, pcs=50.0)
        assert (df["bess_power_ac_kw"].abs() <= prm.pcs_power_kw + 1e-6).all()

    def test_soh_decreases_over_many_cycles(self):
        """SoH phải giảm sau nhiều chu kỳ đầy."""
        # Nạp rồi xả, nhiều lần
        cmds   = (["CHARGE"] * 200 + ["DISCHARGE"] * 200) * 5
        powers = [50.0] * len(cmds)
        df, _  = _run(cmds, powers=powers, soc0=50.0, cap=100.0, pcs=50.0)
        assert df["soh"].iloc[-1] < 100.0


class TestBESSEnergySummary:
    def test_summary_keys(self):
        df, prm = _run(["CHARGE", "DISCHARGE", "IDLE"], powers=[10.0, 10.0, 10.0])
        s = bess_energy_summary(df)
        for k in ["total_charged_kwh", "total_discharged_kwh", "round_trip_eff",
                  "final_soc", "final_soh"]:
            assert k in s

    def test_rte_bounded(self):
        # Bắt đầu từ SoC_min để không có năng lượng dư làm e_out > e_in
        df, prm = _run(["CHARGE"] * 4 + ["DISCHARGE"] * 4,
                       powers=[10.0] * 8, soc0=10.0, soc_min=10.0)
        s = bess_energy_summary(df)
        assert s["round_trip_eff"] >= 0.0
        assert s["round_trip_eff"] <= 1.0 + 1e-6
