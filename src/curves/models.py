"""
src/curves/models.py
Parametric yield curve models (Nelson-Siegel).
"""

import numpy as np
from scipy.optimize import minimize
from typing import Tuple

def nelson_siegel(t: np.ndarray, b0: float, b1: float, b2: float, tau: float) -> np.ndarray:
    """
    Calculates the yield for maturity t using Nelson-Siegel parameters.
    
    t: Time to maturity in years (DU/252)
    b0: Long-term level (Level)
    b1: Short-term component (Slope)
    b2: Medium-term component (Curvature)
    tau: Decay factor
    """
    # Avoids division by zero for very small t
    t = np.where(t < 1e-6, 1e-6, t)
    
    factor = (1 - np.exp(-t / tau)) / (t / tau)
    yield_val = b0 + b1 * factor + b2 * (factor - np.exp(-t / tau))
    return yield_val

def fit_nelson_siegel(t_observed: np.ndarray, y_observed: np.ndarray) -> Tuple[float, float, float, float]:
    """
    Finds the optimal NS parameters that minimize the sum of squared errors 
    between observed market yields and the model.
    """
    
    # Objective function: Mean Squared Error
    def objective(params):
        b0, b1, b2, tau = params
        y_pred = nelson_siegel(t_observed, b0, b1, b2, tau)
        return np.sum((y_observed - y_pred)**2)

    # Initial guesses:
    # b0: often the longest rate
    # b1: shortest rate minus longest rate
    # tau: typically around 1.0 to 2.0 for the BR market
    initial_guess = [y_observed[-1], y_observed[0] - y_observed[-1], 0.0, 1.5]
    
    # Constraints: b0 (long term rate) must be positive, tau must be positive
    bounds = [(0, None), (None, None), (None, None), (0.1, 10.0)]
    
    result = minimize(objective, initial_guess, bounds=bounds, method='L-BFGS-B')
    
    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")
        
    return tuple(result.x)