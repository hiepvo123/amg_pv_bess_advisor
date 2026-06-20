import pytest
from core.modeling_section.models import build_linear_model, build_random_forest_model, build_gradient_boosting_model

def test_model_builders():
    lr = build_linear_model()
    assert lr.steps[-1][0] == 'model'
    
    rf = build_random_forest_model()
    assert rf.steps[-1][0] == 'model'
    
    gb = build_gradient_boosting_model()
    assert gb.steps[-1][0] == 'model'
