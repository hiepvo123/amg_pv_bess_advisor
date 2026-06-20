"""
Model building utilities.
"""
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
import joblib
from pathlib import Path
from core.common.constants import logger

def build_linear_model() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='mean')),
        ('model', LinearRegression())
    ])

def build_random_forest_model(random_state: int = 42) -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='mean')),
        ('model', RandomForestRegressor(n_estimators=100, random_state=random_state))
    ])

def build_gradient_boosting_model(random_state: int = 42) -> Pipeline:
    return Pipeline([
        # HistGradientBoostingRegressor natively handles NaNs, but we impute just in case for consistency
        ('imputer', SimpleImputer(strategy='mean')),
        ('model', HistGradientBoostingRegressor(random_state=random_state))
    ])

def train_model(model: Pipeline, X_train, y_train):
    logger.info(f"Training model: {model.steps[-1][0]}")
    model.fit(X_train, y_train)

def predict_model(model: Pipeline, X_test):
    return model.predict(X_test)

def save_model(model: Pipeline, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    logger.info(f"Saved model to {path}")

def load_model(path: Path) -> Pipeline:
    return joblib.load(path)
