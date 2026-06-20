"""
Reporting logic.
"""
import pandas as pd
from pathlib import Path
from core.common.config import AppConfig
from core.common.constants import logger, ELECTRICITY_PRICE_VND_PER_KWH

def save_summary_report(config: AppConfig, df: pd.DataFrame, irradiance_metrics: pd.DataFrame, power_metrics: pd.DataFrame, output_path: Path):
    """
    Generate and save a markdown summary report.
    """
    logger.info("Generating summary report...")
    
    n_days = df["date"].nunique()
    n_rows = len(df)
    min_date = df["date"].min().strftime('%Y-%m-%d')
    max_date = df["date"].min().strftime('%Y-%m-%d')
    
    missing_pct = (df.isnull().sum() / len(df)) * 100
    missing_str = missing_pct[missing_pct > 0].sort_values(ascending=False).to_string()
    
    report_content = f"""# PV Advisor Summary Report

## Data Quality Summary
- **Date Range**: {min_date} to {max_date}
- **Total Days**: {n_days}
- **Total Rows**: {n_rows}

### Important Data Notes
- **Electricity Price**: Fixed at {ELECTRICITY_PRICE_VND_PER_KWH} VND/kWh.
- **GHI Note**: True GHI data is not available. Using `B.xạ nghiêng` as Plane of Array (POA) Irradiance (`irradiance_poa_wm2`), not as GHI.
- **Load Note**: True load data is not available in the current extracted dataset.

### Missing Values (%)
```text
{missing_str}
```

## Task 1: Irradiance Forecasting Metrics
Next-step POA Irradiance forecasting performance.

```text
{irradiance_metrics.to_string() if not irradiance_metrics.empty else 'No metrics available'}
```

## Task 2: PV Power Prediction Metrics
PV Power generation forecasting performance.

```text
{power_metrics.to_string() if not power_metrics.empty else 'No metrics available'}
```
"""
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    logger.info(f"Report saved to {output_path}")
