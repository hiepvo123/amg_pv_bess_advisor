"""
Training logic for Task 2: PV Power prediction.
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from core.common.config import AppConfig
from core.common.constants import logger
from core.data_section.feature_engineering import make_power_dataset
from core.modeling_section.models import (
    build_linear_model, build_random_forest_model, build_gradient_boosting_model,
    train_model, predict_model, save_model
)
from core.modeling_section.metrics import evaluate_all_day_and_daytime, daily_error_report

def train_power_models(train_df: pd.DataFrame, test_df: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    """Train PV power prediction models."""
    logger.info("Preparing data for PV Power Prediction (Task 2)")
    
    include_tilt = config.pv.tilt_angle_deg is not None
    
    try:
        X_train_df, target_col, features = make_power_dataset(train_df, include_tilt, config.pv.tilt_angle_deg)
        X_test_df, _, _ = make_power_dataset(test_df, include_tilt, config.pv.tilt_angle_deg)
    except ValueError as e:
        logger.error(str(e))
        return pd.DataFrame()
        
    if len(X_train_df) == 0 or len(X_test_df) == 0:
        logger.warning("Not enough data to train power models.")
        return pd.DataFrame()

    y_train = X_train_df[target_col]
    y_test = X_test_df[target_col]
    X_train = X_train_df[features]
    X_test = X_test_df[features]

    results_df = X_test_df[["datetime", "date", "is_daytime", target_col]].copy()
    metrics_list = []
    
    # Baseline: Calculated power if available
    if "p_calc_irr_mw" in X_test_df.columns:
        results_df["pred_baseline"] = X_test_df["p_calc_irr_mw"]
        base_eval = evaluate_all_day_and_daytime(results_df, target_col, "pred_baseline")
        if not base_eval.empty:
            base_eval["Model"] = "Calculated Baseline"
            metrics_list.append(base_eval)

    models = {
        "LinearRegression": build_linear_model(),
        "RandomForest": build_random_forest_model(config.model.random_state),
        "GradientBoosting": build_gradient_boosting_model(config.model.random_state)
    }

    best_r2 = -float("inf")
    best_model_name = None
    
    for name, model in models.items():
        train_model(model, X_train, y_train)
        pred_col = f"pred_{name}"
        results_df[pred_col] = predict_model(model, X_test)
        
        # Power cannot be negative
        results_df.loc[results_df[pred_col] < 0, pred_col] = 0.0
        
        eval_df = evaluate_all_day_and_daytime(results_df, target_col, pred_col)
        eval_df["Model"] = name
        metrics_list.append(eval_df)
        
        all_r2 = eval_df[eval_df["Subset"] == "All"]["R2"].values[0]
        if all_r2 > best_r2:
            best_r2 = all_r2
            best_model_name = name

    final_metrics = pd.concat(metrics_list, ignore_index=True)
    
    if best_model_name:
        logger.info(f"Best power model: {best_model_name} (R2={best_r2:.4f})")
        save_model(models[best_model_name], config.paths.models_dir / "best_power_model.joblib")
        best_pred_col = f"pred_{best_model_name}"
    else:
        # Fallback if somehow ML failed
        best_pred_col = "pred_baseline" if "pred_baseline" in results_df.columns else target_col

    # Save metrics
    final_metrics.to_csv(config.paths.metrics_dir / "power_metrics.csv", index=False)
    
    # Daily Energy Error Report for best model
    energy_report = daily_error_report(results_df, target_col, best_pred_col)
    if not energy_report.empty:
        energy_report.to_csv(config.paths.metrics_dir / "power_daily_energy_error.csv", index=False)
        
    # Save predictions
    results_df.to_csv(config.paths.processed_dir / "power_predictions.csv", index=False)
    
    # Generate Plots
    _plot_power_results(results_df, target_col, best_pred_col, energy_report, config.paths.figures_dir)
    
    return final_metrics

def _plot_power_results(df: pd.DataFrame, target_col: str, pred_col: str, energy_report: pd.DataFrame, figures_dir: Path):
    """Plot power actual vs predicted."""
    # 1. Time series plot
    plt.figure(figsize=(12, 5))
    subset = df.head(500)
    plt.plot(subset["datetime"], subset[target_col], label="Actual", alpha=0.7)
    plt.plot(subset["datetime"], subset[pred_col], label="Predicted", alpha=0.7)
    plt.title("Power: Actual vs Predicted (Time Series Sample)")
    plt.xlabel("Time")
    plt.ylabel("Power (MW)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "power_actual_vs_predicted_ts.png")
    plt.close()

    # 2. Scatter plot
    plt.figure(figsize=(8, 8))
    sns.scatterplot(data=df, x=target_col, y=pred_col, alpha=0.3)
    max_val = max(df[target_col].max(), df[pred_col].max())
    plt.plot([0, max_val], [0, max_val], 'r--')
    plt.title("Power: Actual vs Predicted")
    plt.xlabel("Actual (MW)")
    plt.ylabel("Predicted (MW)")
    plt.tight_layout()
    plt.savefig(figures_dir / "power_actual_vs_predicted_scatter.png")
    plt.close()

    # 3. Residual plot
    plt.figure(figsize=(10, 5))
    residuals = df[target_col] - df[pred_col]
    sns.histplot(residuals, bins=50, kde=True)
    plt.title("Power: Residuals Distribution")
    plt.xlabel("Residual (Actual - Predicted)")
    plt.tight_layout()
    plt.savefig(figures_dir / "power_residuals.png")
    plt.close()

    # 4. Daily MAE / Error
    if not energy_report.empty:
        plt.figure(figsize=(12, 5))
        plt.bar(energy_report["date"].astype(str), energy_report["mae"])
        plt.title("Power: Daily MAE")
        plt.xlabel("Date")
        plt.ylabel("MAE (MW)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(figures_dir / "power_daily_mae.png")
        plt.close()
