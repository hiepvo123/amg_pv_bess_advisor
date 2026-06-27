import os
import sys
import pandas as pd

from pathlib import Path
current_file = Path(__file__).resolve()
project_root = current_file.parent
sys.path.insert(0, str(project_root))

# Import trực tiếp Engine
from core.dispatch_rule import BESSRuleEngine


def run_integrated_demo():
    input_file = project_root / "outputs" / "03_bess_rule_input.csv"

    output_dir = project_root / "outputs"
    output_file = output_dir / "demo_bess_dispatch_output.csv"
    
    # 1. Kiểm tra file dữ liệu đầu vào từ PV Model
    if not os.path.exists(input_file):
        print(f"[ERROR] Khong tim thay file du lieu dau vao: '{input_file}'")
        return

    print(f"[1/3] Dang nap du lieu chuoi thoi gian thuc te tu: {input_file}...")
    df_pv_output = pd.read_csv(input_file)
    
    # 2. Khởi tạo Rule Engine (Lõi này tự import bess_model.py bên trong)
    print("[2/3] Khoi tao BESSRuleEngine & Kich hoat mo phong chuoi vat ly BESS")
    engine = BESSRuleEngine(config=None)
    
    # 3. Thực thi Pipeline điều độ & Tính toán tài chính
    df_result = engine.execute_pipeline(df_pv_output)
    
    # 4. Tổng hợp số liệu thống kê để báo cáo nhanh
    total_records = len(df_result)
    total_revenue = df_result['net_bess_revenue_usd'].sum()
    total_curtailment_mwh = (df_result['pv_curtailment_wasted_mw'].sum()) * 0.5 # dt = 0.5h
    
    # Tính toán sản lượng sạc/xả thực tế từ cột công suất đầu ra của pin (MW * 0.5h = MWh)
    # bess_power_output_mw > 0 là sạc, < 0 là xả
    total_charged_mwh = df_result[df_result['bess_power_output_mw'] > 0]['bess_power_output_mw'].sum() * 0.5
    total_discharged_mwh = abs(df_result[df_result['bess_power_output_mw'] < 0]['bess_power_output_mw'].sum()) * 0.5

    print("KET QUA VAN HANH BESS")
    print(f"Total simulation steps (30-min):  {total_records} steps.")
    print(f"Total energy charged to BESS:     {total_charged_mwh:.2f} MWh")
    print(f"Total energy discharged to grid:  {total_discharged_mwh:.2f} MWh")
    print(f"Wasted solar energy (BESS full):  {total_curtailment_mwh:.2f} MWh")
    print(f"TOTAL ESTIMATED NET REVENUE:      {total_revenue:,.2f} USD")
    
    # 5. Xuất file kết quả cho tầng phân tích tài chính tiếp theo
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"-> Created missing directory: '{output_dir.name}/'")
        
    # Xuất file kết quả vào đúng thư mục đích
    df_result.to_csv(output_file, index=False)
    print(f"\n[SUCCESS] Finalized dispatch streams saved to: '{output_file}'\n")

if __name__ == "__main__":
    run_integrated_demo()