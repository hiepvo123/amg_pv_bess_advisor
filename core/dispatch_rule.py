import pandas as pd

import numpy as np
from core.common.constants import logger

from core.bess_model import BESSModelParams, simulate_bess_series

class BESSRuleEngine:
    def __init__(self, config=None):
        # Khởi tạo tham số cấu hình vật lý
        if config and hasattr(config, 'bess'):
            self.bess_params = BESSModelParams.from_config(config.bess)
        else:
            self.bess_params = BESSModelParams() # Sử dụng mặc định (4MW - 2h = 8000 kWh)
        
        # Biểu giá EVN TOU quy đổi (USD/MWh) theo mô hình SAM
        # Used for financial arbitrage modeling (Off-Peak, Standard, Peak)
        self.tariffs = {
            "OFF_PEAK": {"buy_from_grid": 42.0, "sell_to_grid": 35.0},   # Night-time (22:00 - 04:00)
            "STANDARD": {"buy_from_grid": 76.0, "sell_to_grid": 68.0},   # Normal daytime intervals
            "PEAK": {"buy_from_grid": 152.0, "sell_to_grid": 143.0}      # High tariff intervals (09:30-11:30, 17:00-20:00)
        }

    def get_evn_time_tier(self, hour: int, minute: int = 0) -> str:
        """Categorizes the operating hour according to standard EVN tariff windows."""
        time_val = hour + (minute / 60.0)

        # Khung giờ thấp điểm (Đêm)
        if time_val >= 22.0 or time_val < 4.0:
            return "OFF_PEAK"
        
        # Khung giờ cao điểm (09:30 - 11:30 & 17:00 - 20:00)
        elif (9.5 <= time_val < 11.5) or (17.0 <= time_val < 20.0):
            return "PEAK"
        
        # Các khung giờ còn lại
        return "STANDARD"

    def diagnostics_pv_tracking(self, row) -> tuple:
        """
        Cross-examines real-time plane-of-array (POA) tilt irradiance against measured output 
        from Meter 431 to diagnose shading, tracker blocks, or panel degradation.
        """
        p_actual = row.get('p_meter_431_mw', 0.0)
        irradiance = row.get('irradiance_poa_wm2', 0.0)
        temp_pv = row.get('temp_pv_c', 0.0)
        is_daytime = row.get('is_daytime', False)

        if not is_daytime or pd.isna(irradiance) or irradiance < 40.0:
            return "OK", "Night/Low Irradiance Dormancy"

        ###############
        # Calculate expected clean-sky plant capacity based on temperature derating
        # (mô hình chuẩn ~28.2 MW của Đa Mi)
        p_expected_stc = (irradiance / 1000.0) * 28.2  
        thermal_coefficient = 1.0 - 0.004 * (temp_pv - 25.0) if pd.notna(temp_pv) else 1.0
        p_expected = max(0.0, p_expected_stc * thermal_coefficient)
        ###############

        if p_expected > 0:
            deviation_ratio = p_actual / p_expected
            if deviation_ratio < 0.35:
                return "CRITICAL_FAULT", "Dual-Axis Tracking Actuator Blocked / Severe Shading"
            elif deviation_ratio < 0.75:
                return "WARNING", "Soiling Effect / Dust Accumulation / Panel Hotspot Alert"
            elif deviation_ratio > 1.35:
                return "SENSOR_FAULT", "Meter 431 or POA Pyranometer Calibration Drift"
        
        return "OK", "Optimal Trajectory Efficiency"

    def execute_pipeline(self, df_clean: pd.DataFrame, agc_multiplier: float = 1.0) -> pd.DataFrame:
        """
        Processes the cleaned data timeline to run the multi-layered control dispatch rules
        and output financial and operational columns.
        Tham số:
        agc_multiplier (float): Hệ số bóp tải cho kịch bản độ nhạy
                                (ex: 0.8 tương ứng giảm tải 20%)
        """
        df = df_clean.copy()

        # Đồng bộ hóa dữ liệu thời gian để tính khung giá EVN
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['hour_local'] = df['datetime'].dt.hour
            df['minute_local'] = df['datetime'].dt.minute
        else:
            df['hour_local'] = df.get('hour', 0)
            df['minute_local'] = 0

        n = len(df)
        cmd_list = []
        req_power_kw_list = []
        pv_signals, pv_logs, revenue_streams = [], [], []
        pv_signals = []
        pv_curtailments = []
        pv_logs = []
        reasons = []

        for idx, row in df.iterrows():
            hour = int(row['hour_local'])
            minute = int(row['minute_local'])
            tier = self.get_evn_time_tier(hour, minute)
            
            # Execute PV structural fault analysis layer
            pv_status, pv_msg = self.diagnostics_pv_tracking(row)
            pv_signals.append(pv_status)
            pv_logs.append(pv_msg)

            #############
            # 1. Get the actual real power injected into the grid through breaker bay 431
            p_pv = row.get('p_meter_431_mw', 0.0)
            if pd.isna(p_pv): p_pv = 0.0

            # 2. Extract the AGC Setpoint (giới hạn điều độ lưới điện từ hệ thống AGC)
            # If AGC is missing/empty, assume the grid allows the plant to export at max peak capacity (28.2 MW)
            p_base_limit = row.get('p_setpoint_agc_mw', 28.2)
            if pd.isna(p_base_limit): p_base_limit = 28.2
            # TÍCH HỢP HỆ SỐ ĐỘ NHẠY AGC MULTIPLIER
            p_grid_limit = p_base_limit * agc_multiplier

            # 3. Calculate true excess power that CANNOT be exported to the grid 
            p_excess = p_pv - p_grid_limit
            ############

            cmd = "IDLE"
            req_power_kw = 0.0
            reason = "System Equilibrium"
            reason_prefix = f"AGC_MODIFIED [{p_grid_limit:.1f}MW] | " if agc_multiplier < 1.0 else ""

            # MULTI-LAYERED RULE ENGINE DISPATCH LOGIC
            if pv_status == "CRITICAL_FAULT":
                # Severe plant anomaly -> Lock BESS to stabilize interconnected substation node
                cmd = "IDLE"
                req_power_kw = 0.0
                reason = f"PROTECTION: BESS Locked due to PV Plant Failure [{pv_msg}]"

            else:
                # Setup proper context strings if handling a sensor anomaly
                if pv_status == "SENSOR_FAULT":
                    # Linh hoạt kiếm dữ liệu từ hai nguồn đo dự phòng:
                    # Lấy cột lệnh điều độ của A0 (a0_mw)
                    # Hoặc công suất dự báo từ hệ thống DHD (dhd_mw)
                    # Nếu cả hai đều mất tín hiệu gán bằng 0
                    p_fallback = row.get('a0_mw', row.get('dhd_mw', 0.0))
                    if pd.isna(p_fallback): p_fallback = 0.0
                    p_excess = p_fallback - p_grid_limit
                    reason_prefix += "SENSOR_FALLBACK | "

                # Sạc giá rẻ từ lưới (Thấp điểm)
                if tier == "OFF_PEAK":
                    # Rule 3: Low Price Charging (Grid Ingestion)
                    cmd = "CHARGE"
                    req_power_kw = self.bess_params.pcs_power_kw
                    reason = reason_prefix + "Tariff Optimization: Low-Cost Grid Absorption"

                # Xả kiếm chênh lệch giá (Cao điểm)
                elif tier == "PEAK":
                    # Rule 4: High Price Discharging (Grid Injection Arbitrage)
                    cmd = "DISCHARGE"
                    # Yêu cầu xả tối đa công suất PCS phát lưới giá cao
                    req_power_kw = self.bess_params.pcs_power_kw
                    reason = reason_prefix + "Rule 4: High Price Window Discharging"

                # Hấp thụ công suất bóp tải (Rule 1)
                elif p_excess > 0:
                    cmd = "CHARGE"
                    req_power_kw = p_excess * 1000.0 # Chuyển MW sang kW
                    reason = reason_prefix + "Rule 1: Absorbing Excess Solar Generation"

                # Bù thiếu hụt tải lưới ban ngày (Rule 2)
                elif p_excess < 0:
                    cmd = "DISCHARGE"
                    req_power_kw = abs(p_excess) * 1000.0 # Chuyển MW sang kW
                    reason = reason_prefix + "Rule 2: Discharging to Bridge Generation Deficit"

            # Rule 5 & 6 được xử lý trong bes_model.py: khi BESS đã đạt giới hạn SOC tối đa hoặc tối thiểu

            cmd_list.append(cmd)
            req_power_kw_list.append(req_power_kw)
            reasons.append(reason)
        df['tariff_tier'] = [self.get_evn_time_tier(int(h), int(m)) for h, m in zip(df['hour_local'], df['minute_local'])]
        df['pv_health_status'] = pv_signals
        df['pv_tracking_log'] = pv_logs
        df['decision_justification'] = reasons

        # Chuyển đổi thành dạng Series để khớp cấu hình đầu vào hàm
        bess_cmd_series = pd.Series(cmd_list, index=df.index)
        bess_power_series = pd.Series(req_power_kw_list, index=df.index)
            
        # Đưa sang mô hình bess để mô phỏng
        logger.info("Injecting rules into physical BESS core simulation...")
        bess_sim_df = simulate_bess_series(bess_cmd_series, bess_power_series, self.bess_params)

        # Đóng gói và gộp các cột kết quả vào DataFrame chính
        # Đổi kW về MW để đồng bộ đơn vị công suất với hệ thống SCADA trạm
        df['bess_power_output_mw'] = bess_sim_df['bess_power_ac_kw'] / 1000.0
        df['bess_soc_percentage'] = bess_sim_df['soc']
        df['bess_soc_end_percentage'] = bess_sim_df['soc_end']
        df['bess_soh_percentage'] = bess_sim_df['soh']
        df['rule_engine_decision'] = bess_sim_df['bess_cmd']

        # Thu thập các chỉ số năng lượng tiêu hao tích lũy (kWh)
        df['energy_in_kwh'] = bess_sim_df['energy_in_kwh']
        df['energy_out_kwh'] = bess_sim_df['energy_out_kwh']

        # Tính doanh thu sau suy hao vật lý (Dựa trên công suất AC thực tế đầu ra)
        revenue_streams = []
        pv_curtailments = []

        for idx, row in df.iterrows():
            p_actual_mw = row['bess_power_output_mw']
            tier = row['tariff_tier']
            reason = row['decision_justification']

            p_pv = row.get('p_meter_431_mw', 0.0)
            if pd.isna(p_pv): p_pv = 0.0
            p_grid_limit = row.get('p_setpoint_agc_mw', 28.2) * agc_multiplier
            p_excess = max(0.0, p_pv - p_grid_limit)

            # Tính toán lượng Solar bị cắt giảm lãng phí (wasted curtailment) do pin đầy
            if "Rule 5" in reason or (row['rule_engine_decision'] == "CHARGE" and p_actual_mw < p_excess):
                wasted = p_excess - max(0.0, p_actual_mw)
                pv_curtailments.append(max(0.0, wasted))
            else:
                pv_curtailments.append(0.0)

        # Doanh thu thương mại dựa trên sản lượng điện thực tế đi qua Inverter (MWh)
        # Bước thời gian dt = 0.5h
            if p_actual_mw > 0:  # BESS Sạc điện vào hệ thống pin
                if "Tariff Optimization" in reason:
                    # Nếu mua sạc từ lưới điện quốc gia
                    cost = p_actual_mw * 0.5 * self.tariffs[tier]["buy_from_grid"]
                    revenue_streams.append(-cost)
                else:
                    # Sạc từ Solar bóp tải thừa -> Miễn phí
                    revenue_streams.append(0.0)
            
            elif p_actual_mw < 0:  # BESS Xả điện phát ngược lên lưới
                # Tiền thu được từ việc bán điện xả từ pin lên lưới
                rev = abs(p_actual_mw) * 0.5 * self.tariffs[tier]["sell_to_grid"]
                revenue_streams.append(rev)
            else:
                revenue_streams.append(0.0)

        df['pv_curtailment_wasted_mw'] = pv_curtailments
        df['net_bess_revenue_usd'] = revenue_streams

        return df