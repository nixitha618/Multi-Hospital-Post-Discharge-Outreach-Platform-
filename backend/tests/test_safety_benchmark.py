import pytest
from backend.app.safety.runner import safety_runner

def test_zero_false_negatives_benchmark():
    """
    Critical Clinical Safety Test:
    Asserts that across the fixed safety dataset of 35 cases,
    NO urgent or concerning patient is missed (Zero False Negatives, FNR = 0.0%).
    """
    results = safety_runner.run_benchmark()
    
    assert results["false_negatives"] == 0, f"Critical Safety Failure: Detected {results['false_negatives']} false negative(s)!"
    assert results["false_negative_rate_percentage"] == 0.0
    assert results["sensitivity_percentage"] == 100.0
    assert results["safety_status"] == "EXCELLENT (0% FNR)"
