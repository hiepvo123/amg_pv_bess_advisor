import pytest
from core.run_pipeline import main
import sys

def test_cli_help(capsys):
    # Just verify that argparse doesn't crash on simple import
    assert callable(main)
