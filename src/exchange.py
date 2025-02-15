import ccxt.async_support as ccxt
import pandas as pd
import logging
import asyncio
import sys
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
import time

# Fix for Windows SelectorEventLoop issue
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Exchange:
    def __init__(self, api_key, api_secret, trading_mode='spot'):
        """
        Initialize the Binance exchange asynchronously.

        :param api_key: API key for the exchange.
        :param api_secret: API secret for the exchange.
        :param trading_mode: Trading mode, either 'spot' or 'margin'. Defaults to 'spot'.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.trading_mode = trading_mode

        # Initialize the exchange client
        self.session = aiohttp.ClientSession()
        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "session": self.session,
            'options': {
                'defaultType': trading_mode,  # Set trading mode (spot or margin)
            },
        })

    async def fetch_binance_server_time(self):
        """
        Fetch the current server time from Binance.
        """
        try:
            server_time = await self.safe_fetch(self.exchange.public_get_time)
            return server_time["serverTime"]
        except Exception as e:
            logger.error(f"❌ Failed to fetch Binance server time: {e}")
            return None

    async def close(self):
        """Properly close the exchange connection asynchronously."""
        await self.exchange.close()
        await self.session.close()

    async def safe_fetch(self, func, *args, **kwargs):
        """Wrapper to retry API calls while avoiding recursion issues."""
        retries = kwargs.pop("retries", 3)
        delay = kwargs.pop("delay", 2)

        for i in range(retries):
            try:
                # Only sync time if calling a non-time related function
                if func != self.exchange.public_get_time and not self.exchange.options.get("adjustForTimeDifference"):
                    await self.sync_time()

                return await func(*args, **kwargs)

            except (ccxt.NetworkError, ccxt.DDoSProtection, ccxt.RequestTimeout) as e:
                logger.warning(f"⚠️ Network issue during {func.__name__}: {e}. Retrying {i+1}/{retries}...")
            except ccxt.ExchangeError as e:
                logger.error(f"❌ Exchange error during {func.__name__}: {e}")
                break  # Stop retries on critical exchange errors
            except Exception as e:
                logger.error(f"❌ Unexpected error during {func.__name__}: {e}")
                break  # Stop retries for unknown errors
            await asyncio.sleep(delay)

        logger.error("❌ Max retries reached. Request failed.")
        return None

    async def fetch_latest_price(self, symbol):
        """Fetch the latest market price for a given trading pair."""
        ticker = await self.safe_fetch(self.exchange.fetch_ticker, symbol)
        return ticker['last'] if ticker else None

    async def fetch_ohlcv(self, symbol, timeframe, limit=100):
        """Fetch OHLCV data while ensuring Binance time sync."""
        if not self.exchange.options.get("adjustForTimeDifference"):
            await self.sync_time()  # Call time sync only if needed

        retries = 3
        delay = 2

        for i in range(retries):
            try:
                ohlcv = await self.safe_fetch(self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
                if not ohlcv or len(ohlcv) == 0:
                    logger.warning(f"⚠️ No OHLCV data received for {symbol}. Returning empty dataset.")
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                logger.info(f"✅ Successfully fetched OHLCV data for {symbol} ({timeframe}). Latest close: {df['close'].iloc[-1]}")
                return df

            except Exception as e:
                logger.error(f"❌ Error fetching OHLCV data (attempt {i+1}/{retries}): {e}")
                if i < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error("❌ Max retries reached. Returning empty dataset.")
                    return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])  # Fallback return

    async def check_balance(self, symbol: str, required_balance: float) -> dict:
        """Check and return balance instead of just True/False."""
        balance = await self.safe_fetch(self.fetch_balance)  # ✅ Fetch balance correctly

        if not balance:
            logger.error("❌ Failed to fetch balance.")
            return {}  # ✅ Return an empty dictionary instead of False

        base_currency, quote_currency = symbol.split("/")
        base_balance = balance["total"].get(base_currency, 0)
        quote_balance = balance["total"].get(quote_currency, 0)

        if base_balance >= required_balance or quote_balance >= required_balance:
            logger.info(f"✅ Sufficient balance for {symbol}. Required: {required_balance}, Available: {base_balance} {base_currency} / {quote_balance} {quote_currency}")

        else:
            logger.warning(f"⚠️ Insufficient balance for {symbol}. Needed: {required_balance}, Available: {base_balance} {base_currency} / {quote_balance} {quote_currency}")

        return balance  # ✅ Return the full balance dictionary

    async def get_min_trade_size(self, symbol):
        """Fetches the minimum trade size (quote currency value) for a trading pair."""
        markets = await self.safe_fetch(self.exchange.load_markets)
        if markets:
            market = markets.get(symbol)
            return market["limits"]["cost"]["min"] if market and "limits" in market and "cost" in market["limits"] else None
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def place_market_order(self, symbol, side, amount):
        """
        Places a market order for spot trading asynchronously with retries.

        Args:
            symbol (str): The trading pair (e.g., 'BTC/USDT').
            side (str): The order side ('buy' or 'sell').
            amount (float): The amount of the base currency to trade.

        Returns:
            dict: The order details if successful, otherwise None.
        """
        try:
            # Validate order parameters
            if not symbol or not side or amount <= 0:
                logger.error(f"❌ Invalid order parameters: symbol={symbol}, side={side}, amount={amount}")
                return None

            # Fetch current market price and calculate slippage
            ticker = await self.safe_fetch(self.exchange.fetch_ticker, symbol)
            current_price = ticker['last']
            slippage = 0.001  # 0.1% slippage
            adjusted_price = current_price * (1 + slippage) if side == 'buy' else current_price * (1 - slippage)

            # Calculate fees (e.g., 0.1% fee)
            fee_rate = 0.001
            fee = amount * adjusted_price * fee_rate

            # Adjust amount for fees
            if side == 'buy':
                amount -= fee / adjusted_price
            else:
                amount -= fee / adjusted_price

            # Place the order
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount
            )
            logger.info(f"✅ Market {side} order executed for {amount} {symbol} at ~{adjusted_price}")
            return order
        except Exception as e:
            logger.error(f"❌ Error placing market order: {e}")
            return None

    async def place_margin_order(self, symbol, side, amount):
        """Places a cross-margin order with risk management (avoids liquidation)."""
        try:
            base_currency, quote_currency = symbol.split("/")
            binance_symbol = symbol.replace("/", "")

            # Fetch margin account details
            margin_info = await self.safe_fetch(self.exchange.sapi_get_margin_account)
            if not margin_info:
                logger.error("❌ Failed to fetch margin account details.")
                return None

            margin_assets = {asset["asset"]: asset for asset in margin_info["userAssets"]}
            base_balance = float(margin_assets.get(base_currency, {}).get("free", 0))
            quote_balance = float(margin_assets.get(quote_currency, {}).get("free", 0))

            margin_level = float(margin_info["marginLevel"])
            if margin_level < 1.2:
                logger.error("❌ Margin level too low! Trading halted to avoid liquidation.")
                return None

            latest_price = await self.fetch_latest_price(symbol)
            if not latest_price:
                logger.error(f"❌ Could not fetch latest price for {symbol}. Order aborted.")
                return None

            if side == "sell":
                if base_balance < amount:
                    borrow_amount = amount - base_balance
                    await self.safe_fetch(self.exchange.sapi_post_margin_loan, params={"asset": base_currency, "amount": borrow_amount})
                    logger.info(f"✅ Borrowed {borrow_amount} {base_currency} for shorting.")

                order = await self.safe_fetch(self.exchange.sapi_post_margin_order, params={
                    "symbol": binance_symbol,
                    "side": "SELL",
                    "type": "MARGIN",
                    "quantity": amount,
                    "isIsolated": "FALSE"
                })
                logger.info(f"✅ Short position executed: {amount} {base_currency} sold.")
                return order

            elif side == "buy":
                required_funds = amount * latest_price
                if quote_balance < required_funds:
                    borrow_amount = required_funds - quote_balance
                    await self.safe_fetch(self.exchange.sapi_post_margin_loan, params={"asset": quote_currency, "amount": borrow_amount})
                    logger.info(f"✅ Borrowed {borrow_amount} {quote_currency} for buying {base_currency}.")

                order = await self.safe_fetch(self.exchange.sapi_post_margin_order, params={
                    "symbol": binance_symbol,
                    "side": "BUY",
                    "type": "MARGIN",
                    "quantity": amount,
                    "isIsolated": "FALSE"
                })
                logger.info(f"✅ Long position executed: {amount} {base_currency} bought.")
                return order

        except Exception as e:
            logger.error(f"❌ Error placing {side} margin order for {amount} {symbol}: {e}")
            return None

    async def sync_time(self):
        """Sync exchange time with Binance to prevent timestamp errors."""
        try:
            server_time = await self.safe_fetch(self.exchange.public_get_time)

            if not server_time:
                logger.error("❌ Failed to sync Binance server time. Skipping time adjustment.")
                return

            binance_time = int(server_time['serverTime']) // 1000  # Convert to seconds
            local_time = int(time.time())

            time_diff = binance_time - local_time
            logger.info(f"🕒 Time sync: Adjusting local time difference by {time_diff} seconds.")

            # Apply time adjustment safely
            self.exchange.options['adjustForTimeDifference'] = True
            self.exchange.options['timestamp'] = binance_time * 1000  # Ensure it's in ms

        except Exception as e:
            logger.error(f"❌ Error syncing Binance time: {e}")