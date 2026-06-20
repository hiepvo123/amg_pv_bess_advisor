"""
Exploratory Data Analysis (EDA) plotting functions.
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from core.common.constants import logger

def plot_daily_max_irradiance(df: pd.DataFrame, output_path: Path):
    if "irradiance_poa_wm2" not in df.columns or "date" not in df.columns:
        return
        
    plt.figure(figsize=(10, 5))
    daily_max = df.groupby("date")["irradiance_poa_wm2"].max()
    daily_max.plot(kind='bar', color='orange')
    plt.title("Daily Maximum POA Irradiance")
    plt.xlabel("Date")
    plt.ylabel("Max Irradiance (W/m²)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_average_profile_by_hour(df: pd.DataFrame, column: str, output_path: Path):
    if column not in df.columns or "hour_float" not in df.columns:
        return
        
    plt.figure(figsize=(10, 5))
    avg_profile = df.groupby("hour_float")[column].mean()
    plt.plot(avg_profile.index, avg_profile.values, marker='o', linestyle='-')
    plt.title(f"Average Daily Profile: {column}")
    plt.xlabel("Hour of Day")
    plt.ylabel(column)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_irradiance_vs_power(df: pd.DataFrame, output_path: Path):
    if "irradiance_poa_wm2" not in df.columns:
        return
        
    power_col = "p_meter_431_mw" if "p_meter_431_mw" in df.columns else "p_431_mw"
    if power_col not in df.columns:
        return
        
    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df, x="irradiance_poa_wm2", y=power_col, alpha=0.5)
    plt.title("POA Irradiance vs PV Power")
    plt.xlabel("POA Irradiance (W/m²)")
    plt.ylabel(f"Power ({power_col})")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_temperature_vs_power(df: pd.DataFrame, output_path: Path):
    if "temp_pv_c" not in df.columns:
        return
        
    power_col = "p_meter_431_mw" if "p_meter_431_mw" in df.columns else "p_431_mw"
    if power_col not in df.columns:
        return
        
    plt.figure(figsize=(8, 6))
    # Optionally filter to daytime
    day_df = df[df.get("is_daytime", pd.Series(True, index=df.index))]
    sns.scatterplot(data=day_df, x="temp_pv_c", y=power_col, alpha=0.5, color='red')
    plt.title("PV Temperature vs PV Power (Daytime)")
    plt.xlabel("PV Temperature (°C)")
    plt.ylabel(f"Power ({power_col})")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path):
    numeric_df = df.select_dtypes(include=['float64', 'int64', 'float32', 'int32'])
    if numeric_df.empty:
        return
        
    plt.figure(figsize=(12, 10))
    corr = numeric_df.corr()
    sns.heatmap(corr, annot=False, cmap='coolwarm', fmt=".2f")
    plt.title("Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_missing_values(df: pd.DataFrame, output_path: Path):
    plt.figure(figsize=(12, 6))
    missing_pct = (df.isnull().sum() / len(df)) * 100
    missing_pct = missing_pct[missing_pct > 0].sort_values(ascending=False)
    
    if missing_pct.empty:
        logger.info("No missing values to plot.")
        return
        
    sns.barplot(x=missing_pct.values, y=missing_pct.index, palette="viridis", hue=missing_pct.index, legend=False)
    plt.title("Percentage of Missing Values")
    plt.xlabel("% Missing")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def run_eda(df: pd.DataFrame, figures_dir: Path):
    """Run all EDA plots."""
    logger.info("Running EDA plots...")
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    plot_daily_max_irradiance(df, figures_dir / "daily_max_irradiance.png")
    
    if "irradiance_poa_wm2" in df.columns:
        plot_average_profile_by_hour(df, "irradiance_poa_wm2", figures_dir / "avg_profile_irradiance.png")
    
    plot_irradiance_vs_power(df, figures_dir / "irradiance_vs_power.png")
    plot_temperature_vs_power(df, figures_dir / "temperature_vs_power.png")
    plot_correlation_heatmap(df, figures_dir / "correlation_heatmap.png")
    plot_missing_values(df, figures_dir / "missing_values.png")
