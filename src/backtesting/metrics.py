# File: backtesting/metrics.py
import numpy as np

def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """
    Calculates the Sharpe ratio.
    
    Args:
        returns (list): List of returns.
        risk_free_rate (float): Risk-free rate.
    
    Returns:
        float: Sharpe ratio.
    """
    excess_returns = np.array(returns) - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns)

def calculate_sortino_ratio(returns, risk_free_rate=0.0):
    """
    Calculates the Sortino ratio.
    
    Args:
        returns (list): List of returns.
        risk_free_rate (float): Risk-free rate.
    
    Returns:
        float: Sortino ratio.
    """
    excess_returns = np.array(returns) - risk_free_rate
    downside_returns = excess_returns[excess_returns < 0]
    return np.mean(excess_returns) / np.std(downside_returns)