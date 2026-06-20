"""
Script to extract rows where p_meter_431_mw is missing in the raw dataset.
"""
import pandas as pd
from core.common.config import AppConfig
from core.data_section.file_discovery import find_month_files
from core.data_section.excel_reader import read_many_daily_files
from core.data_section.data_cleaning import to_number

def extract_missing_meter_rows():
    config = AppConfig()
    
    # 1. Discover all files
    file_dict = find_month_files(config)
    all_files = file_dict["train"] + file_dict["test"]
    
    if not all_files:
        print("No files found!")
        return
        
    print("Reading raw data from Excel files...")
    raw_df = read_many_daily_files(all_files)
    
    # Apply the same string-to-number cleaning to figure out what results in NaN
    raw_df["p_meter_431_mw_numeric"] = raw_df["p_meter_431_mw"].apply(to_number)
    
    # Find rows where the cleaned number is NaN
    missing_meter_df = raw_df[raw_df["p_meter_431_mw_numeric"].isna()].copy()
    
    # Save to CSV
    output_csv = config.paths.outputs_dir / "raw_missing_meter_rows.csv"
    config.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    
    cols_to_print = [
        "datetime", "date", "source_file", "cycle", "time_range", 
        "irradiance_poa_wm2", "p_431_mw", "p_meter_431_mw"
    ]
    
    missing_meter_df[cols_to_print].to_csv(output_csv, index=False, encoding="utf-8-sig")
    
    print(f"\nFound {len(missing_meter_df)} rows where the meter data is missing or invalid.")
    print(f"Saved to: {output_csv}\n")
    
    # Group by date to see which days are most affected
    summary = missing_meter_df.groupby("date").size().reset_index(name="missing_cycles")
    print("--- Missing Meter Data Summary by Date ---")
    print(summary.to_string(index=False))

if __name__ == "__main__":
    extract_missing_meter_rows()
