import unittest
import pandas as pd
import numpy as np

import sys
from pathlib import Path

# Thêm thư mục gốc của dự án vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dispatch_rule import BESSRuleEngine


class TestBESSRuleEngine(unittest.TestCase):

    def setUp(self):
        #Khởi tạo môi trường kiểm thử trước mỗi test case
        self.engine = BESSRuleEngine(config=None)

    def test_evn_time_tier(self):
        #Kiểm tra tính chính xác của việc phân loại khung giờ TOU EVN
        # Thấp điểm ban đêm
        self.assertEqual(self.engine.get_evn_time_tier(23, 0), "OFF_PEAK")
        self.assertEqual(self.engine.get_evn_time_tier(1, 30), "OFF_PEAK")
        
        # Cao điểm
        self.assertEqual(self.engine.get_evn_time_tier(10, 0), "PEAK")
        self.assertEqual(self.engine.get_evn_time_tier(9, 30), "PEAK")
        self.assertEqual(self.engine.get_evn_time_tier(18, 15), "PEAK")
        
        # Bình thường
        self.assertEqual(self.engine.get_evn_time_tier(8, 0), "STANDARD")
        self.assertEqual(self.engine.get_evn_time_tier(14, 0), "STANDARD")

    def test_execute_pipeline_logic(self):
        """Kiểm tra luồng xử lý dữ liệu và ra quyết định điều độ của Engine."""
        
        # Giả lập DataFrame đầu vào chuẩn schema của file 03_bess_rule_input.csv
        mock_data = {
            "timestamp": [
                "2025-03-01 01:00:00",  # 1. Khung Thấp điểm - Mua sạc từ lưới
                "2025-03-01 10:00:00",  # 2. Khung Cao điểm - Xả phát lưới kiếm lời
                "2025-03-01 13:00:00",  # 3. Khung Bình thường - Thừa Solar -> Sạc pin (Rule 1)
                "2025-03-01 15:00:00"   # 4. Khung Bình thường - Thiếu Solar -> Xả bù tải (Rule 2)
            ],
            "P_PV_MW": [0.0, 5.0, 20.0, 2.0],
            "P_load_MW": [25.0, 25.0, 5.0, 10.0],
            "P_surplus_MW": [0.0, 0.0, 15.0, 0.0],  # Thừa 15MW lúc 13:00
            "P_deficit_MW": [25.0, 20.0, 0.0, 8.0]   # Thiếu 8MW lúc 15:00
        }
        df_input = pd.DataFrame(mock_data)

        # Chạy thử nghiệm
        df_output = self.engine.execute_pipeline(df_input)

        # KIỂM TRA 1: THẤP ĐIỂM ĐÊM
        # Phải phát lệnh sạc đầy công suất PCS (4MW = 4000kW)
        self.assertEqual(df_output.iloc[0]['rule_engine_decision'], "CHARGE")
        # Doanh thu âm do phải chi trả tiền điện sạc đêm cho lưới
        self.assertLess(df_output.iloc[0]['net_bess_revenue_usd'], 0)

        # KIỂM TRA 2: CAO ĐIỂM SÁNG
        # Phải phát lệnh xả tối đa công suất PCS lên lưới giá cao
        self.assertEqual(df_output.iloc[1]['rule_engine_decision'], "DISCHARGE")
        # Doanh thu dương lớn do bán được điện giá cao peak
        self.assertGreater(df_output.iloc[1]['net_bess_revenue_usd'], 0)

        # KIỂM TRA 3: THỪA SOLAR BAN NGÀY (Rule 1)
        # Phải phát lệnh sạc để hấp thụ lượng điện thừa
        self.assertEqual(df_output.iloc[2]['rule_engine_decision'], "CHARGE")
        # Sạc từ solar thừa -> Miễn phí mua điện từ lưới -> Doanh thu bằng 0
        self.assertEqual(df_output.iloc[2]['net_bess_revenue_usd'], 0.0)

        # KIỂM TRA 4: THIẾU SOLAR BAN NGÀY (Rule 2)
        # Phải phát lệnh xả để bù vào khoảng hụt tải của trạm
        self.assertEqual(df_output.iloc[3]['rule_engine_decision'], "DISCHARGE")
        # Xả lên lưới/tải nội bộ giờ standard -> Doanh thu bán điện dương
        self.assertGreater(df_output.iloc[3]['net_bess_revenue_usd'], 0)

    def test_missing_columns_handling(self):
        """Đảm bảo hệ thống tự gán giá trị 0.0 nếu khuyết thiếu dữ liệu surplus/deficit."""
        mock_data = {
            "timestamp": ["2025-03-01 13:00:00"],
            "P_PV_MW": [20.0],
            "P_load_MW": [5.0],
            "P_surplus_MW": [np.nan],  # Dữ liệu lỗi dính NaN
            "P_deficit_MW": [np.nan]   # Dữ liệu lỗi dính NaN
        }
        df_input = pd.DataFrame(mock_data)
        
        # Thực thi không được ném ra exception lỗi toán học float + NaN
        try:
            df_output = self.engine.execute_pipeline(df_input)
            success = True
        except Exception:
            success = False
            
        self.assertTrue(success)
        # Dính NaN hệ thống đưa về Equilibrium -> IDLE
        self.assertEqual(df_output.iloc[0]['rule_engine_decision'], "IDLE")


if __name__ == "__main__":
    unittest.main()