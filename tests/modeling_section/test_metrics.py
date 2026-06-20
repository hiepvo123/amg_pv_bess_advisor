import pytest
import numpy as np
from core.modeling_section.metrics import regression_metrics

def test_regression_metrics():
    y_true = np.array([3, -0.5, 2, 7])
    y_pred = np.array([2.5, 0.0, 2, 8])
    metrics = regression_metrics(y_true, y_pred)
    
    assert "MAE" in metrics
    assert "RMSE" in metrics
    assert "R2" in metrics
    assert metrics["MAE"] == 0.5
