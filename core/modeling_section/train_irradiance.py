"""
Training logic for Task 1: Irradiance forecasting.
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from core.common.config import AppConfig
from core.common.constants import logger
from core.data_section.feature_engineering import make_irradiance_dataset
from core.modeling_section.models import (
    build_linear_model, build_random_forest_model, build_gradient_boosting_model,
    train_model, predict_model, save_model
)
from core.modeling_section.metrics import evaluate_all_day_and_daytime

def train_irradiance_models(train_df: pd.DataFrame, test_df: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    """Train irradiance forecasting models."""
    logger.info("Preparing data for Irradiance Forecasting (Task 1)")
    
    X_train_df, target_col, features = make_irradiance_dataset(train_df)
    X_test_df, _, _ = make_irradiance_dataset(test_df)
    
    if len(X_train_df) == 0 or len(X_test_df) == 0:
        logger.warning("Not enough data to train irradiance models.")
        return pd.DataFrame()

    y_train = X_train_df[target_col]
    y_test = X_test_df[target_col]
    X_train = X_train_df[features]
    X_test = X_test_df[features]

    # Initialize results dataframe for predictions
    results_df = X_test_df[["datetime", "date", "is_daytime", target_col]].copy()
    
    # 1. Baseline: Persistence (next irradiance = current irradiance)
    results_df["pred_persistence"] = X_test_df["irradiance_poa_wm2"]
    
    models = {
        "LinearRegression": build_linear_model(),
        "RandomForest": build_random_forest_model(config.model.random_state),
        "GradientBoosting": build_gradient_boosting_model(config.model.random_state)
    }

    metrics_list = []
    
    # Evaluate Baseline
    base_eval = evaluate_all_day_and_daytime(results_df, target_col, "pred_persistence")
    base_eval["Model"] = "Persistence"
    metrics_list.append(base_eval)

    # Train and evaluate ML models
    best_r2 = -float("inf")
    best_model_name = None
    
    for name, model in models.items():
        train_model(model, X_train, y_train)
        pred_col = f"pred_{name}"
        results_df[pred_col] = predict_model(model, X_test)
        
        # Evaluate
        eval_df = evaluate_all_day_and_daytime(results_df, target_col, pred_col)
        eval_df["Model"] = name
        metrics_list.append(eval_df)
        
        # Track best model based on All R2
        all_r2 = eval_df[eval_df["Subset"] == "All"]["R2"].values[0]
        if all_r2 > best_r2:
            best_r2 = all_r2
            best_model_name = name

    # Combine metrics
    final_metrics = pd.concat(metrics_list, ignore_index=True)
    
    # Save best model
    if best_model_name:
        logger.info(f"Best irradiance model: {best_model_name} (R2={best_r2:.4f})")
        save_model(models[best_model_name], config.paths.models_dir / "best_irradiance_model.joblib")
        best_pred_col = f"pred_{best_model_name}"
    else:
        best_pred_col = "pred_persistence"

    # Save metrics
    final_metrics.to_csv(config.paths.metrics_dir / "irradiance_metrics.csv", index=False)
    
    # Save predictions
    results_df.to_csv(config.paths.processed_dir / "irradiance_predictions.csv", index=False)
    
    # Generate Plots
    _plot_irradiance_results(results_df, target_col, best_pred_col, config.paths.figures_dir)
    
    return final_metrics

def _plot_irradiance_results(df: pd.DataFrame, target_col: str, pred_col: str, figures_dir: Path):
    """Plot irradiance actual vs predicted."""
    # 1. Time series plot (subset first 500 points for clarity if large)
    plt.figure(figsize=(12, 5))
    subset = df.head(500)
    plt.plot(subset["datetime"], subset[target_col], label="Actual", alpha=0.7)
    plt.plot(subset["datetime"], subset[pred_col], label="Predicted", alpha=0.7)
    plt.title("Irradiance: Actual vs Predicted (Time Series Sample)")
    plt.xlabel("Time")
    plt.ylabel("Irradiance POA (W/m²)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "irradiance_actual_vs_predicted_ts.png")
    plt.close()

    # 2. Scatter plot
    plt.figure(figsize=(8, 8))
    sns.scatterplot(data=df, x=target_col, y=pred_col, alpha=0.3)
    max_val = max(df[target_col].max(), df[pred_col].max())
    plt.plot([0, max_val], [0, max_val], 'r--')
    plt.title("Irradiance: Actual vs Predicted")
    plt.xlabel("Actual")
    plt.ylabel("Predicted")
    plt.tight_layout()
    plt.savefig(figures_dir / "irradiance_actual_vs_predicted_scatter.png")
    plt.close()

    # 3. Residual plot
    plt.figure(figsize=(10, 5))
    residuals = df[target_col] - df[pred_col]
    sns.histplot(residuals, bins=50, kde=True)
    plt.title("Irradiance: Residuals Distribution")
    plt.xlabel("Residual (Actual - Predicted)")
    plt.tight_layout()
    plt.savefig(figures_dir / "irradiance_residuals.png")
    plt.close()
