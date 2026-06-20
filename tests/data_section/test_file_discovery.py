import pytest
import pandas as pd
from pathlib import Path
from core.data_section.file_discovery import parse_date_from_filename

def test_parse_date_from_filename():
    path = Path("some/folder/Bao cao ngay DHD 31-03-2025.xlsx")
    date_val = parse_date_from_filename(path)
    assert date_val.year == 2025
    assert date_val.month == 3
    assert date_val.day == 31
    
def test_parse_date_invalid_filename():
    path = Path("some/folder/invalid_name.xlsx")
    date_val = parse_date_from_filename(path)
    assert pd.isna(date_val)
