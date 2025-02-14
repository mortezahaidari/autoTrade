# File: backtesting/visualization.py
import matplotlib.pyplot as plt

def plot_equity_curve(equity_curve):
    """
    Plots the equity curve.
    
    Args:
        equity_curve (list): List of account balances over time.
    """
    plt.figure(figsize=(10, 6))
    plt.plot(equity_curve, label="Equity Curve")
    plt.title("Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Balance")
    plt.legend()
    plt.grid()
    plt.show()

def plot_trade_history(data, trades):
    """
    Plots the trade history on the price chart.
    
    Args:
        data (pd.DataFrame): Historical OHLCV data.
        trades (list): List of trades.
    """
    plt.figure(figsize=(10, 6))
    plt.plot(data['close'], label="Price")
    
    for trade in trades:
        if trade['type'] == 'buy':
            plt.scatter(trade['timestamp'], trade['price'], color='green', label="Buy", marker='^')
        elif trade['type'] == 'sell':
            plt.scatter(trade['timestamp'], trade['price'], color='red', label="Sell", marker='v')
    
    plt.title("Trade History")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.grid()
    plt.show()