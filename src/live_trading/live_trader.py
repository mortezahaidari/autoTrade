import logging
import asyncio
from exchange import Exchange
from utils.notifications import send_telegram_message_with_retries

logger = logging.getLogger(__name__)


class LiveTrader:
    def __init__(self, exchange, symbol, trading_mode="spot"):
        self.exchange = exchange
        self.symbol = symbol
        self.trading_mode = trading_mode
        self.position = 0  # Current position


async def execute_trade(self, signal, current_price):
    """
    Executes a trade on the exchange based on the given signal.
    
    Args:
        signal (str): Trading signal (e.g., 'buy', 'sell').
        current_price (float): Current price of the asset.
    """
    if signal == 'buy' and self.position == 0:
        # Place buy order
        order = await self.exchange.create_order(
            symbol=self.symbol,
            type='market',
            side='buy',
            amount=self.calculate_position_size(current_price)  # Calculate position size
        )
        self.position = order['filled']  # Update position
        logger.info(f"📈 BUY order executed at ${current_price:.2f}")

    elif signal == 'sell' and self.position > 0:
        # Place sell order
        order = await self.exchange.create_order(
            symbol=self.symbol,
            type='market',
            side='sell',
            amount=self.position
        )
        self.position = 0  # Close position
        logger.info(f"📉 SELL order executed at ${current_price:.2f}")