"""
File discovery logic to locate and parse Excel files.
"""
from pathlib import Path
import pandas as pd
import re
from core.common.config import AppConfig
from core.common.constants import logger

def parse_date_from_filename(path: Path) -> pd.Timestamp:
    """
    Parse date from file name.
    Example: 'Bao cao ngay DHD 31-03-2025.xlsx'
    """
    name = path.stem
    match = re.search(r"(\d{2}-\d{2}-\d{4})", name)
    if match:
        date_str = match.group(1)
        return pd.to_datetime(date_str, format="%d-%m-%Y")
    else:
        logger.warning(f"Could not parse date from filename: {path.name}")
        return pd.NaT

def find_excel_files(folder_path: Path) -> list[Path]:
    """Find all Excel files in the specified folder recursively."""
    if not folder_path.exists():
        logger.warning(f"Folder does not exist: {folder_path}")
        return []
    
    files = list(folder_path.glob("**/*.xlsx"))
    files = [f for f in files if not f.name.startswith("~")]  # ignore temporary Excel files
    logger.info(f"Found {len(files)} Excel files in {folder_path}")
    return sorted(files)

def find_month_files(config: AppConfig) -> dict[str, list[Path]]:
    """Discover files for train (March) and test (April)."""
    train_folder = config.paths.data_root / config.paths.march_folder
    test_folder = config.paths.data_root / config.paths.april_folder
    
    return {
        "train": find_excel_files(train_folder),
        "test": find_excel_files(test_folder),
    }
