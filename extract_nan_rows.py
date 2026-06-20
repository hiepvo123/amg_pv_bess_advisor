"""
Script to extract specific rows with missing temperature data from the raw dataset
and save them to a CSV file for manual review.
"""
import pandas as pd
from core.common.config import AppConfig
from core.data_section.file_discovery import find_month_files
from core.data_section.excel_reader import read_many_daily_files

def extract_missing_temp_rows():
    config = AppConfig()
    
    # 1. Discover all files
    file_dict = find_month_files(config)
    all_files = file_dict["train"] + file_dict["test"]
    
    if not all_files:
        print("No files found!")
        return
        
    # 2. Read the raw extracted data (before cleaning)
    print("Reading raw data from Excel files...")
    raw_df = read_many_daily_files(all_files)
    
    # 3. Define the specific targets you want to find (by date and cycle)
    # Based on the rows you provided:
    targets = [
        ("2025-03-03", 3),
        ("2025-03-08", 26),
        ("2025-03-08", 31),
        ("2025-03-17", 27),
        ("2025-04-13", 45),
        ("2025-04-16", 41),
        ("2025-04-18", 3),
        ("2025-04-25", 12),
    ]
    
    # Convert target dates to pandas datetime for matching
    target_dates = pd.to_datetime([t[0] for t in targets])
    target_cycles = [str(t[1]) for t in targets] # Cycles are often strings in raw df
    
    # 4. Filter the raw_df to find these specific rows
    # We match where (date is in target_dates) AND (cycle is in target_cycles)
    # A more precise way is to match the exact tuple of (date, cycle)
    
    # Create a helper column to match tuples
    raw_df["_match_key"] = list(zip(pd.to_datetime(raw_df["date"]), raw_df["cycle"].astype(str)))
    target_keys = list(zip(target_dates, target_cycles))
    
    suspect_rows = raw_df[raw_df["_match_key"].isin(target_keys)].copy()
    
    # Drop the helper column
    suspect_rows = suspect_rows.drop(columns=["_match_key"])
    
    # 5. Alternatively, just find all rows where temp_air_c or temp_pv_c is missing, '-', or empty in raw data
    # (Commented out, but you can use this to find all similar issues)
    # suspect_rows = raw_df[
    #    (raw_df["temp_air_c"].isin(["-", "", None]) | raw_df["temp_air_c"].isna()) |
    #    (raw_df["temp_pv_c"].isin(["-", "", None]) | raw_df["temp_pv_c"].isna())
    # ]
    
    # 6. Save to CSV
    output_csv = config.paths.outputs_dir / "raw_suspect_rows.csv"
    config.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    
    # Select columns of interest for easier reading
    cols_to_print = [
        "datetime", "date", "source_file", "cycle", "time_range", 
        "temp_air_c", "temp_pv_c", "irradiance_poa_wm2", "p_meter_431_mw"
    ]
    
    # Only keep columns that actually exist
    cols_to_print = [c for c in cols_to_print if c in suspect_rows.columns]
    
    suspect_rows[cols_to_print].to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\nFound {len(suspect_rows)} matching raw rows.")
    print(f"Saved exact raw representations to: {output_csv}")
    
    print("\nPreview:")
    print(suspect_rows[cols_to_print])

if __name__ == "__main__":
    extract_missing_temp_rows()
