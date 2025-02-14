import logging

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self, initial_balance=10000, commission=0.001):
        self.balance = initial_balance
        self.commission = commission
        self.position = 0
        self.trades = []

    async def execute_trade(self, signal, current_price):
        """
        Executes a trade in a paper trading environment.
        
        Args:
            signal (str): Trading signal (e.g., 'buy', 'sell').
            current_price (float): Current price of the asset.
        """
        if signal == 'buy' and self.position == 0:
            # Execute buy order
            self.position = self.balance / current_price
            self.balance = 0
            self.trades.append({'type': 'buy', 'price': current_price, 'timestamp': pd.Timestamp.now()})
            logger.info(f"📈 Paper Trade: BUY {self.position:.2f} units at ${current_price:.2f}")
        elif signal == 'sell' and self.position > 0:
            # Execute sell order
            self.balance = self.position * current_price * (1 - self.commission)
            self.position = 0
            self.trades.append({'type': 'sell', 'price': current_price, 'timestamp': pd.Timestamp.now()})
            logger.info(f"📉 Paper Trade: SELL at ${current_price:.2f}, Balance: ${self.balance:.2f}")