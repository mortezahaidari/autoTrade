# File: backtesting/run_backtest.py
from backtester import Backtester
from visualization import plot_equity_curve, plot_trade_history
from strategies.combined_signal import CombinedStrategy
from utils.logger import logger
from src.exchange import fetch_ohlcv

# Fetch historical data (assuming you have a function for this)
data = fetch_ohlcv("BTCUSDT", "1h", "2023-01-01", "2023-10-01")

# Generate signals
strategy = CombinedStrategy()
signals = strategy.generate_signals(data)

# Run backtest
backtester = Backtester(initial_balance=10000, commission=0.001, trade_size=0.1)
results = backtester.backtest(data, signals)

# Visualize results
plot_equity_curve(results['equity_curve'])
plot_trade_history(data, results['trades'])