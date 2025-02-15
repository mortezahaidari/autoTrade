# File: backtesting/metrics.py
import numpy as np

import numpy as np

def calculate_sharpe_ratio(excess_returns):
    mean_returns = np.mean(excess_returns)
    std_returns = np.std(excess_returns)

    if std_returns == 0:
        return np.nan  # or handle it as appropriate for your use case
    if np.isnan(mean_returns) or np.isnan(std_returns):
        return np.nan  # or handle it as appropriate for your use case

    return mean_returns / std_returns


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


def calculate_max_drawdown(equity_curve):
    peak = equity_curve[0]
    max_drawdown = 0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def calculate_profit_factor(trades):
    gross_profit = sum(trade['profit'] for trade in trades if trade['profit'] > 0)
    gross_loss = abs(sum(trade['profit'] for trade in trades if trade['profit'] < 0))
    return gross_profit / gross_loss if gross_loss != 0 else float('inf')