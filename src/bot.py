import asyncio
import logging
import os
import pandas as pd
import msvcrt
from datetime import datetime
from dotenv import load_dotenv

from exchange import Exchange
from strategies.strategy_factory import StrategyFactory
from live_trading.live_trader import LiveTrader
from utils.notifications import send_telegram_message_with_retries
import config
import traceback

# Additional imports for other modes (if needed)
from backtesting.backtester import Backtester
from backtesting.optimization import optimize_parameters
from backtesting.visualization import plot_equity_curve, plot_trade_history
from paper_trading.paper_trader import PaperTrader

# Import feature engineering for data preprocessing
from ml_models.feature_engineering import preprocess_data

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Event to signal exit without blocking the event loop
stop_event = asyncio.Event()

async def listen_for_exit():
    """Listen for user input (press 'q') to gracefully stop the bot."""
    logger.info("🛑 Press 'q' to stop the bot.")
    while not stop_event.is_set():
        if os.name == "nt":  # Windows
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'q':
                    logger.info("🛑 Exit signal received. Stopping bot...")
                    stop_event.set()
        await asyncio.sleep(0.1)

def attach_fetch_balance(exchange_instance):
    """
    Attach a fetch_balance method to the Exchange instance.
    
    Although your exchange.py only provides check_balance, the underlying
    ccxt client does have a fetch_balance method. This helper wraps it with
    the safe_fetch function and assigns it to exchange_instance.
    """
    async def fetch_balance(*args, **kwargs):
        # Call the ccxt client's fetch_balance via safe_fetch
        return await exchange_instance.safe_fetch(exchange_instance.exchange.fetch_balance, *args, **kwargs)
    exchange_instance.fetch_balance = fetch_balance

async def main(mode="live_trade"):
    logger.info("🚀 Starting AutoTrade bot...")
    load_dotenv()  # Load environment variables

    # Initialize the exchange using API keys from your environment
    exchange = Exchange(
        os.getenv("BINANCE_API_KEY"),
        os.getenv("BINANCE_API_SECRET"),
        trading_mode="spot"
    )
    # Attach a fetch_balance method to our Exchange instance
    attach_fetch_balance(exchange)

    # For multiple-symbol trading, define symbols as a list.
    # Here we assume config.SYMBOL (e.g. "BTC/USDT") is defined in your config.
    symbols = [config.SYMBOL]

    # Initialize your trading strategy
    strategy = StrategyFactory.get_strategy("combined")

    # Start the exit listener task
    exit_listener = asyncio.create_task(listen_for_exit())

    try:
        # Fetch and preprocess historical data (for backtesting, signal generation, etc.)
        historical_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe="1d", limit=1000)
        historical_data = pd.DataFrame(
            historical_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        historical_data['timestamp'] = pd.to_datetime(historical_data['timestamp'], unit='ms')
        logger.info(f"Historical Data Columns: {historical_data.columns}")
        logger.info(f"Sample Data:\n{historical_data.tail()}")

        # Preprocess the data (this function may drop or adjust rows as needed)
        historical_data = preprocess_data(historical_data)
        logger.info(f"Preprocessed Data Columns: {historical_data.columns}")
        logger.info(f"Sample Preprocessed Data:\n{historical_data.tail()}")

        # Generate strategy signals based on historical data
        strategy_signals = strategy.generate_signals(historical_data)
        logger.info(f"Data length: {len(historical_data)}")
        logger.info(f"Signals length: {len(strategy_signals)}")
        logger.info(f"Sample signals: {strategy_signals.head()}")

        if mode == "backtest":
            backtester = Backtester(initial_balance=100, commission=0.01, trade_size=0.5)
            backtest_results = backtester.backtest(historical_data, strategy_signals)
            logger.info(f"📊 Backtest Results: {backtest_results}")
            plot_equity_curve(backtest_results['equity_curve'])
            plot_trade_history(historical_data, backtest_results['trades'])

        elif mode == "paper_trade":
            paper_trader = PaperTrader()
            while not stop_event.is_set():
                try:
                    live_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME)
                    live_data = pd.DataFrame(
                        live_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    live_data['timestamp'] = pd.to_datetime(live_data['timestamp'], unit='ms')
                    live_data = preprocess_data(live_data)
                    signals = strategy.generate_signals(live_data)
                    latest_signal = signals.iloc[-1]
                    current_price = live_data['close'].iloc[-1]

                    logger.info(f"Live data: {live_data.tail()}")
                    logger.info(f"Latest signal: {latest_signal}")

                    await paper_trader.execute_trade(latest_signal, current_price)
                    logger.info("🔁 Waiting for the next cycle...")
                    await asyncio.sleep(60)  # Adjust sleep time based on your timeframe

                except Exception as e:
                    logger.error(f"⚠️ Error in paper trading loop: {e}")
                    await asyncio.sleep(10)

        elif mode == "live_trade":
            # Track whether we have placed the first trade
            first_trade_executed = False
            # Initialize LiveTrader instance **before** the loop
            live_trader = LiveTrader(exchange, symbols, trading_mode="spot", risk_percentage=0.1)
            while not stop_event.is_set():
                try:
                    # Fetch live data
                    live_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME)
                    live_data = pd.DataFrame(
                        live_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    live_data['timestamp'] = pd.to_datetime(live_data['timestamp'], unit='ms')
                    live_data = preprocess_data(live_data)
                    signals = strategy.generate_signals(live_data)
                    latest_signal = signals.iloc[-1]  # Get the most recent signal
                    current_price = live_data['close'].iloc[-1]

                    logger.info(f"Live data: {live_data.tail()}")
                    logger.info(f"Latest signal: {latest_signal}")

                    # Check if a first trade has been made
                    balance = await exchange.fetch_balance()  # Fetch balance to check if we hold any asset

                    base_currency = config.SYMBOL.split("/")[0]  # Extract "BTC" from "BTC/USDT"
                    quote_currency = config.SYMBOL.split("/")[1]  # Extract "USDT" from "BTC/USDT"

                    base_balance = balance.get(base_currency, 0)  # Amount of BTC held
                    quote_balance = balance.get(quote_currency, 0)  # Amount of USDT held

                    logger.info(f"Current Balance: {base_currency}: {base_balance}, {quote_currency}: {quote_balance}")

                    if base_balance == 0 and not first_trade_executed:
                        # If we have no base asset (BTC) and no trade has been made yet, we must start
                        logger.info(f"🚀 No position detected! Placing first trade: BUY {base_currency}")

                        await live_trader.execute_trade(config.SYMBOL, "BUY", current_price)

                        first_trade_executed = True  # Mark that we've placed the first trade

                    else:
                        # If we already have a position, continue trading normally
                        await live_trader.execute_trade(config.SYMBOL, latest_signal, current_price)

                    logger.info("🔁 Waiting for the next cycle...")
                    await asyncio.sleep(60)  # Adjust sleep time based on timeframe

                except Exception as e:
                    logger.error(f"⚠️ Error in live trading loop: {traceback.format_exc()}")
                    await asyncio.sleep(10)  # Retry after delay

        elif mode == "optimize":
            trade_sizes = [0.05, 0.1, 0.2]
            commissions = [0.0005, 0.001, 0.002]
            best_params = optimize_parameters(historical_data, trade_sizes, commissions)
            logger.info(f"🎯 Best Parameters: {best_params}")

    finally:
        exit_listener.cancel()
        await exchange.close()
        logger.info("✅ Exchange connection closed.")

if __name__ == "__main__":
    # Run the bot in live trading mode
    asyncio.run(main(mode="live_trade"))
