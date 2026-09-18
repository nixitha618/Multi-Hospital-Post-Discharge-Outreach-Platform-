from typing import Dict, Any
from fastapi import APIRouter
from backend.app.safety.runner import safety_runner

router = APIRouter(prefix="/safety", tags=["Safety Benchmark & Evaluation"])

@router.get("/benchmark")
async def run_safety_benchmark() -> Dict[str, Any]:
    """
    Executes the 35 fixed evaluation test cases across routine, red-flag,
    ambiguous, incomplete, conflicting, and adversarial prompt injection scenarios.
    Reports Confusion Matrix, Sensitivity, Specificity, and False-Negative Rate (FNR).
    """
    results = safety_runner.run_benchmark()
    return results
