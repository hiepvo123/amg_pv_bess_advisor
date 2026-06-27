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

    def execute_pipeline(self, df_clean: pd.DataFrame) -> pd.DataFrame:
        """
        Processes the cleaned data timeline to run the multi-layered control dispatch rules
        and output financial and operational columns.
        """
        df = df_clean.copy()

        # Đồng bộ hóa dữ liệu thời gian để tính khung giá EVN
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour_local'] = df['timestamp'].dt.hour
            df['minute_local'] = df['timestamp'].dt.minute
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['hour_local'] = df['datetime'].dt.hour
            df['minute_local'] = df['datetime'].dt.minute
        else:
            df['hour_local'] = df.get('hour', 0)
            df['minute_local'] = 0

        n = len(df)
        cmd_list = []
        req_power_kw_list = []
        pv_signals = []
        pv_logs = []
        reasons = []

        for idx, row in df.iterrows():
            hour = int(row['hour_local'])
            minute = int(row['minute_local'])
            tier = self.get_evn_time_tier(hour, minute)
            
            # đọc chẩn đoán sức khỏe PV
            p_pv = row.get('P_PV_MW', 0.0)
            if pd.isna(p_pv): p_pv = 0.0

            # Map tạm thời các trường chẩn đoán
            pv_status, pv_msg = "OK", "Optimal Trajectory Efficiency"
            pv_signals.append(pv_status)
            pv_logs.append(pv_msg)

            # Lấy lượng điện thặng dư / thiếu hụt đã được tính toán sẵn từ file của đồng đội
            p_surplus = row.get('P_surplus_MW', 0.0)
            p_deficit = row.get('P_deficit_MW', 0.0)

            # Xử lý an toàn NaN cho dữ liệu thô
            if pd.isna(p_surplus): p_surplus = 0.0
            if pd.isna(p_deficit): p_deficit = 0.0

            cmd = "IDLE"
            req_power_kw = 0.0
            reason = "System Equilibrium"


            # Sạc giá rẻ từ lưới (Thấp điểm)
            if tier == "OFF_PEAK":
                # Rule 3: Low Price Charging (Grid Ingestion)
                cmd = "CHARGE"
                req_power_kw = self.bess_params.pcs_power_kw
                reason = "Rule 3: Low-Cost Grid Absorption"

            # Xả kiếm chênh lệch giá (Cao điểm)
            elif tier == "PEAK":
                # Rule 4: High Price Discharging (Grid Injection Arbitrage)
                cmd = "DISCHARGE"
                # Yêu cầu xả tối đa công suất PCS phát lưới giá cao
                req_power_kw = self.bess_params.pcs_power_kw
                reason = "Rule 4: High Price Window Discharging"

            # Hấp thụ công suất bóp tải (Rule 1)
            elif p_surplus > 0:
                cmd = "CHARGE"
                req_power_kw = p_surplus * 1000.0 # Chuyển MW sang kW
                reason = "Rule 1: Absorbing Excess Solar Generation"

            # Bù thiếu hụt tải lưới ban ngày (Rule 2)
            elif p_deficit > 0:
                cmd = "DISCHARGE"
                req_power_kw = p_deficit * 1000.0 # Chuyển MW sang kW
                reason = "Rule 2: Discharging to Bridge Generation Deficit"

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
            p_surplus = row.get('P_surplus_MW', 0.0)

            # Tính toán lượng Solar bị cắt giảm lãng phí (wasted curtailment) do pin đầy
            if row['rule_engine_decision'] == "CHARGE" and p_actual_mw < p_surplus:
                wasted = p_surplus - max(0.0, p_actual_mw)
                pv_curtailments.append(max(0.0, wasted))
            else:
                pv_curtailments.append(0.0)

        # Doanh thu từ việc sạc/xả pin theo khung giá EVN
        # Bước thời gian dt = 0.5h
            if p_actual_mw > 0:  # BESS Sạc điện vào hệ thống pin
                if "Rule 3" in reason:
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