"""
Excel reader to parse the specific 48-cycle operational table from DMS sheets.
"""
import pandas as pd
from pathlib import Path
from core.common.constants import logger, EXPECTED_COLUMNS
from core.data_section.file_discovery import parse_date_from_filename

def read_daily_dhd_file(path: Path) -> pd.DataFrame:
    """
    Read the DMS sheet from the daily DHD file and extract the 48-cycle operational table.
    Fails fast (raises exception) if data extraction fails.
    """
    try:
        # We use header=None because of merged cells and complex headers
        df_raw = pd.read_excel(path, sheet_name="DMS", header=None)
    except Exception as e:
        logger.error(f"Failed to read sheet 'DMS' in {path}: {e}")
        raise ValueError(f"Core data extraction failed for {path.name}") from e

    # Find the operational table
    # We look for rows where the first column is a cycle number from 1 to 48
    # and the second column contains a time range like '00:00 - 00:30' or '06:30 - 07:00'
    table_rows = []
    
    for idx, row in df_raw.iterrows():
        col0 = str(row[0]).strip()
        col1 = str(row[1]).strip()
        
        # Check if col0 is a digit between 1 and 48
        if col0.isdigit() and 1 <= int(col0) <= 48:
            # Check if col1 looks like a time range
            if "-" in col1 and ":" in col1:
                table_rows.append(row.values)

    if len(table_rows) < 48:
        logger.error(f"Found only {len(table_rows)}/48 cycles in {path.name}")
        if len(table_rows) == 0:
            raise ValueError(f"Could not locate the operational table in {path.name}")

    # Extract the first 18 columns
    try:
        df_table = pd.DataFrame(table_rows).iloc[:, :18]
        df_table.columns = EXPECTED_COLUMNS
    except Exception as e:
        logger.error(f"Failed to extract 18 expected columns in {path.name}: {e}")
        raise ValueError(f"Core data column extraction failed for {path.name}") from e

    # Add metadata
    date_val = parse_date_from_filename(path)
    df_table["date"] = date_val
    df_table["source_file"] = path.name

    # Create proper datetime column from date and start of time_range
    def parse_datetime(row):
        try:
            # Extract start time, e.g., '06:30' from '06:30 - 07:00'
            start_time_str = str(row["time_range"]).split("-")[0].strip()
            # If start time is 24:00, handle it as next day's 00:00
            if start_time_str.startswith("24:00"):
                dt = pd.to_datetime(f"{row['date'].strftime('%Y-%m-%d')} 00:00") + pd.Timedelta(days=1)
            else:
                dt = pd.to_datetime(f"{row['date'].strftime('%Y-%m-%d')} {start_time_str}")
            return dt
        except Exception:
            return pd.NaT

    df_table["datetime"] = df_table.apply(parse_datetime, axis=1)
    
    # Drop rows where datetime could not be parsed
    df_table = df_table.dropna(subset=["datetime"]).copy()
    
    # Add explicit time features
    df_table["month"] = df_table["datetime"].dt.month
    df_table["day"] = df_table["datetime"].dt.day
    df_table["hour"] = df_table["datetime"].dt.hour
    df_table["minute"] = df_table["datetime"].dt.minute
    df_table["day_of_year"] = df_table["datetime"].dt.dayofyear

    return df_table

def read_many_daily_files(files: list[Path]) -> pd.DataFrame:
    """Read and concatenate multiple daily Excel files."""
    dfs = []
    for f in files:
        logger.info(f"Reading file: {f.name}")
        try:
            df = read_daily_dhd_file(f)
            dfs.append(df)
        except Exception as e:
            logger.error(f"Skipping {f.name} due to error: {e}")
            raise # Fail fast as requested
            
    if not dfs:
        raise ValueError("No valid data could be extracted from the provided files.")
        
    final_df = pd.concat(dfs, ignore_index=True)
    final_df = final_df.sort_values("datetime").reset_index(drop=True)
    return final_df
