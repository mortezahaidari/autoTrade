import logging
import asyncio
from exchange import Exchange
from utils.notifications import send_telegram_message_with_retries

logger = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self, exchange, symbols, trading_mode="spot", risk_percentage=0.1):
        """
        Initialize the LiveTrader with multiple symbols.

        :param exchange: The Exchange instance for API interactions.
        :param symbols: List of trading pairs (e.g., ["BTC/USDT", "ETH/USDT"]).
        :param trading_mode: Trading mode, either 'spot' or 'margin'. Defaults to 'spot'.
        :param risk_percentage: Risk percentage per trade. Defaults to 0.1 (10%).
        """
        self.exchange = exchange
        self.symbols = symbols
        self.trading_mode = trading_mode
        self.risk_percentage = risk_percentage
        self.positions = {symbol: 0 for symbol in symbols}  # Track positions for each symbol


    async def calculate_position_size(self, symbol, current_price):
        """
        Calculate the position size for a specific symbol based on available balance and risk per trade.
        """
        balance = await self.exchange.check_balance(symbol, required_balance=0)

        if not balance or not isinstance(balance, dict):
            logger.error("❌ check_balance() returned an invalid response. Expected a dictionary.")
            return 0.0

        _, quote_currency = symbol.split("/")  # e.g., BTC/USDT → quote_currency = USDT

        # ✅ Correct way to access free balance
        available_balance = balance.get("free", {}).get(quote_currency, 0)

        logger.info(f"🔢 Available {quote_currency} balance: {available_balance}")  # Debug log

        if available_balance <= 10:  # Minimum trade threshold
            logger.warning(f"⚠️ Insufficient {quote_currency} balance to trade {symbol}.")
            return 0.0

        # ✅ Calculate position size based on risk percentage
        position_size = (available_balance * self.risk_percentage) / current_price
        return position_size


    async def manage_risk(self, symbol, current_price):
        """
        Adjust stop-loss and take-profit dynamically for a specific symbol.
        """
        position = self.positions.get(symbol, 0)
        if position > 0:
            stop_loss = current_price * 0.98  # 2% stop-loss
            take_profit = current_price * 1.05  # 5% take-profit

            # Place stop-loss and take-profit orders
            try:
                await self.exchange.place_order(
                    symbol=symbol,
                    side='sell',
                    amount=position,
                    type='stop_loss_limit',
                    stop_price=stop_loss,
                    price=stop_loss
                )
                await self.exchange.place_order(
                    symbol=symbol,
                    side='sell',
                    amount=position,
                    type='take_profit_limit',
                    stop_price=take_profit,
                    price=take_profit
                )
                logger.info(f"🎯 Updated stop-loss: ${stop_loss:.2f}, take-profit: ${take_profit:.2f} for {symbol}")
            except Exception as e:
                logger.error(f"❌ Failed to place stop-loss/take-profit orders for {symbol}: {e}")

    async def execute_trade(self, symbol, signal, current_price):
        """
        Execute a trade for a specific symbol based on the signal.
        """
        position_size = await self.calculate_position_size(symbol, current_price)
        logger.info(f"💰 Calculated position size for {symbol}: {position_size}")  # Debug log

        if position_size <= 0:
            logger.warning(f"⚠️ Position size is 0 for {symbol}. No trade will be executed.")
            return

        if signal == 'buy' and self.positions[symbol] == 0:
            logger.info(f"🛒 Attempting to BUY {position_size} {symbol} at {current_price}")  # Debug log
            order = await self.exchange.execute_trade(symbol, 'buy', position_size)
            if order:
                self.positions[symbol] = order['filled']
                logger.info(f"✅ BUY order executed for {symbol} at ${current_price:.2f} with size {position_size}")

        elif signal == 'sell' and self.positions[symbol] > 0:
            logger.info(f"📤 Attempting to SELL {self.positions[symbol]} {symbol} at {current_price}")  # Debug log
            order = await self.exchange.execute_trade(symbol, 'sell', self.positions[symbol])
            if order:
                self.positions[symbol] = 0
                logger.info(f"✅ SELL order executed for {symbol} at ${current_price:.2f}")


    async def trade_multiple_symbols(self, signals):
        """
        Trade multiple symbols concurrently based on signals.

        :param signals: Dictionary of signals for each symbol (e.g., {"BTC/USDT": "buy", "ETH/USDT": "sell"}).
        """
        tasks = []
        for symbol, signal in signals.items():
            if symbol not in self.symbols:
                logger.warning(f"⚠️ Symbol {symbol} not in the configured symbols list.")
                continue

            # Fetch the latest price for the symbol
            current_price = await self.exchange.fetch_latest_price(symbol)
            if not current_price:
                logger.error(f"❌ Failed to fetch latest price for {symbol}. Skipping trade.")
                continue

            logger.info(f"🔍 Preparing to trade {symbol}: {signal} at {current_price:.2f}")  # Debug log

            # Execute the trade
            tasks.append(self.execute_trade(symbol, signal, current_price))

        # Run all trades concurrently
        await asyncio.gather(*tasks)
