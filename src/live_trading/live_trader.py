import logging
import asyncio
from exchange import Exchange
from utils.notifications import send_telegram_message_with_retries

logger = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self, exchange, symbol, trading_mode="spot", risk_percentage=0.1):
        self.exchange = exchange
        self.symbol = symbol
        self.trading_mode = trading_mode
        self.position = 0
        self.risk_percentage = risk_percentage

    async def calculate_position_size(self, current_price):
        """Calculate position size based on account balance and risk percentage."""
        required_balance = 10.0
        balance = await self.exchange.check_balance(self.symbol, required_balance )
        risk_amount = balance * self.risk_percentage
        position_size = risk_amount / current_price
        logger.info(f"📐 Calculated position size: {position_size:.4f}")
        return round(position_size, 6)

    async def execute_trade(self, signal, current_price, amount):
        """
        Executes a trade on the exchange based on the given signal.
        
        Args:
            signal (str): Trading signal ('buy', 'sell').
            current_price (float): Current price of the asset.
        """
        try:
            position_size = await self.calculate_position_size(current_price)

            if signal == 'buy' and self.position == 0:
                # Place buy order
                order = await self.exchange.place_margin_order(
                    symbol=self.symbol,
                    type='market',
                    side='buy',
                    amount=position_size
                )
                self.position = order['filled']
                logger.info(f"📈 BUY order executed at ${current_price:.2f} with size {position_size}")

                # Send notification
                await send_telegram_message_with_retries(f"BUY order executed at ${current_price:.2f}")

            elif signal == 'sell' and self.position > 0:
                # Place sell order
                order = await self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=position_size
                )
                self.position = 0
                logger.info(f"📉 SELL order executed at ${current_price:.2f}")

                # Send notification
                await send_telegram_message_with_retries(f"SELL order executed at ${current_price:.2f}")

            else:
                logger.info(f"⚖️ No action taken (signal: {signal}, position: {self.position})")

        except Exception as e:
            logger.error(f"❌ Trade execution failed: {e}")
            await send_telegram_message_with_retries(f"⚠️ Trade execution failed: {e}")

    async def manage_risk(self, current_price):
        """Adjust stop-loss and take-profit dynamically based on market conditions."""
        if self.position > 0:
            stop_loss = current_price * 0.98  # 2% stop-loss
            take_profit = current_price * 1.05  # 5% take-profit
            logger.info(f"🎯 Updated stop-loss: ${stop_loss:.2f}, take-profit: ${take_profit:.2f}")

    async def monitor_market(self):
        """Continuously monitor the market and adjust trades if necessary."""
        while True:
            current_price = await self.exchange.fetch_latest_price(self.symbol)
            logger.info(f"📊 Current market price: ${current_price:.2f}")
            await self.manage_risk(current_price)
            await asyncio.sleep(60)  # Check every 60 seconds
