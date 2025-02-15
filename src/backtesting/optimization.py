# File: backtesting/optimization.py
from backtesting.backtester import Backtester
from strategies.combined_signal import CombinedStrategy
from exchange import Exchange
import logging

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# File: backtesting/optimization.py
def optimize_parameters(data, trade_sizes, commissions):
    """
    Optimizes trade size and commission parameters.
    
    Args:
        data (pd.DataFrame): Historical OHLCV data.
        trade_sizes (list): List of trade sizes to test.
        commissions (list): List of commissions to test.
    
    Returns:
        dict: Best parameters and results.
    """
    best_roi = -float('inf')
    best_params = {}

    for trade_size in trade_sizes:
        for commission in commissions:
            logger.info(f"Testing trade_size={trade_size}, commission={commission}")

            strategy = CombinedStrategy()
            signals = strategy.generate_signals(data)
            
            backtester = Backtester(initial_balance=10000, commission=commission, trade_size=trade_size)
            results = backtester.backtest(data, signals)
            
            logger.info(f"Results for trade_size={trade_size}, commission={commission}: {results}")

            if results['roi'] > best_roi:
                best_roi = results['roi']
                best_params = {
                    'trade_size': trade_size,
                    'commission': commission,
                    'results': results
                }
    
    return best_params
    

# Example usage
#if __name__ == "__main__":
 #   data = Exchange.fetch_ohlcv("BTCUSDT", "1h", "2023-01-01", "2023-10-01")
  #  trade_sizes = [0.05, 0.1, 0.2]  # Test different trade sizes
   # commissions = [0.0005, 0.001, 0.002]  # Test different commissions
  #  
  #  best_params = optimize_parameters(data, trade_sizes, commissions)
  #  print("Best Parameters:")
  #  print(best_params)