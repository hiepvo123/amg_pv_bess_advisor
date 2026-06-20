"""
Main pipeline orchestrator.
"""
import argparse
import sys
from pathlib import Path
import pandas as pd

from core.common.config import AppConfig, PathConfig
from core.common.constants import logger
from core.data_section.file_discovery import find_month_files
from core.data_section.excel_reader import read_many_daily_files
from core.data_section.data_cleaning import clean_operational_dataframe
from core.data_section.feature_engineering import add_time_features, add_lag_features
from core.data_section.data_split import split_train_test
from core.data_section.eda import run_eda
from core.modeling_section.train_irradiance import train_irradiance_models
from core.modeling_section.train_power import train_power_models
from core.reporting_section.reporting import save_summary_report

def main():
    parser = argparse.ArgumentParser(description="PV BESS Advisor Data Pipeline")
    parser.add_argument("--data-root", type=str, default="data/solarelectric_data", help="Root directory for data")
    parser.add_argument("--skip-eda", action="store_true", help="Skip running EDA plots")
    parser.add_argument("--skip-training", action="store_true", help="Skip model training")
    parser.add_argument("--tilt-angle-deg", type=float, default=None, help="PV Panel Tilt Angle (Degrees)")
    args = parser.parse_args()

    logger.info("Starting PV BESS Advisor Pipeline")
    
    # Configuration
    config = AppConfig()
    config.paths.data_root = Path(args.data_root)
    config.pv.tilt_angle_deg = args.tilt_angle_deg
    config.create_output_dirs()
    
    # 1. Discover files
    file_dict = find_month_files(config)
    all_files = file_dict["train"] + file_dict["test"]
    
    if not all_files:
        logger.error(f"No Excel files found in {config.paths.data_root}")
        sys.exit(1)
        
    # 2. Read and extract core data
    try:
        raw_df = read_many_daily_files(all_files)
    except Exception as e:
        logger.error(f"Pipeline stopped due to core data extraction failure: {e}")
        sys.exit(1)
        
    # 3. Clean data
    logger.info("Cleaning data...")
    clean_df = clean_operational_dataframe(raw_df)
    
    # 4. Feature engineering
    logger.info("Adding features...")
    feat_df = add_time_features(clean_df)
    feat_df = add_lag_features(feat_df)
    
    # Save processed dataframe
    processed_path = config.paths.processed_dir / "pv_30min_clean.csv"
    feat_df.to_csv(processed_path, index=False)
    logger.info(f"Saved processed dataset to {processed_path}")
    
    # 5. Split train/test
    try:
        train_df, test_df = split_train_test(feat_df)
    except Exception as e:
        logger.error(f"Data split failed: {e}")
        sys.exit(1)

    # 6. EDA
    if not args.skip_eda:
        run_eda(feat_df, config.paths.figures_dir)
        
    irradiance_metrics = pd.DataFrame()
    power_metrics = pd.DataFrame()
    
    # 7. Modeling
    if not args.skip_training:
        try:
            irradiance_metrics = train_irradiance_models(train_df, test_df, config)
        except Exception as e:
            logger.error(f"Task 1 Irradiance training failed: {e}")
            
        try:
            power_metrics = train_power_models(train_df, test_df, config)
        except Exception as e:
            logger.error(f"Task 2 Power training failed: {e}")
            
    # 8. Reporting
    report_path = config.paths.outputs_dir / "summary_report.md"
    save_summary_report(config, feat_df, irradiance_metrics, power_metrics, report_path)
    
    logger.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
