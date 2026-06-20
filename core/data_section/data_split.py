"""
Data splitting logic.
"""
import pandas as pd
from core.common.constants import logger

def split_train_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split the dataset into train (March 2025) and test (April 2025).
    """
    if "month" not in df.columns or "datetime" not in df.columns:
        raise ValueError("DataFrame must contain 'month' and 'datetime' columns for splitting.")
        
    # Strictly filter for the year 2025 just in case
    df_2025 = df[df["datetime"].dt.year == 2025].copy()
    
    train_df = df_2025[df_2025["month"] == 3].copy()
    test_df = df_2025[df_2025["month"] == 4].copy()
    
    logger.info(f"Split data: Train (March) has {len(train_df)} rows, Test (April) has {len(test_df)} rows.")
    
    return train_df, test_df
