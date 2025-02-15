import asyncio
import logging
import os
import pandas as pd
import msvcrt
from datetime import datetime
from dotenv import load_dotenv
from exchange import Exchange
from strategies.strategy_factory import StrategyFactory
from risk_management.position_sizing import calculate_position_size
from risk_management.stop_loss import set_stop_loss
from risk_management.trailing_stop import update_trailing_stop
from utils.logger import setup_logger
from utils.notifications import send_telegram_message_with_retries  # Import from notifications.py
import config  # Import config.py
import traceback
from backtesting.backtester import Backtester
from paper_trading.paper_trader import PaperTrader
from live_trading.live_trader import LiveTrader
# In bot.py
from ml_models.feature_engineering import preprocess_data  # Add this line
# File: bot.py
from backtesting.backtester import Backtester
from backtesting.optimization import optimize_parameters
from backtesting.visualization import plot_equity_curve, plot_trade_history

# Load environment variables
load_dotenv()

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

stop_event = asyncio.Event()  # Event to signal stopping

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


""" &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& """
async def listen_for_exit():
    """Listen for user input to stop the bot without blocking execution."""
    logger.info("🛑 Press 'q' to stop the bot.")

    while not stop_event.is_set():
        if os.name == "nt":  # Windows
            if msvcrt.kbhit():  # Check if a key was pressed
                key = msvcrt.getch()
                if key == b'q':  # If 'q' is pressed
                    logger.info("🛑 Exit signal received. Stopping bot...")
                    stop_event.set()
        await asyncio.sleep(0.1)  # Small delay to prevent CPU overuse


""" &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& """




async def main(mode="backtest"):
    """Main function for executing the trading bot."""
    logger.info("🚀 Starting AutoTrade bot...")

    # Initialize exchange
    exchange = Exchange(
        os.getenv("BINANCE_API_KEY"),
        os.getenv("BINANCE_API_SECRET"),
        trading_mode="spot"
    )

    try:
        # Start the exit listener
        exit_listener = asyncio.create_task(listen_for_exit())

        # Fetch historical data
        historical_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe="1d", limit=1000)
        historical_data = pd.DataFrame(historical_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        historical_data['timestamp'] = pd.to_datetime(historical_data['timestamp'], unit='ms')

        # In bot.py (before generating signals)
        logger.info(f"Historical Data Columns: {historical_data.columns}")
        logger.info(f"Sample Data:\n{historical_data.tail()}")
        
        # Preprocess data (this may drop rows with NaN values)
        historical_data = preprocess_data(historical_data)

        # Log preprocessed data
        logger.info(f"Preprocessed Data Columns: {historical_data.columns}")
        logger.info(f"Sample Preprocessed Data:\n{historical_data.tail()}")

        # Initialize strategy
        strategy = StrategyFactory.get_strategy("combined")

        # Generate signals AFTER preprocessing
        strategy_signals = strategy.generate_signals(historical_data)
        # Debug: Check lengths
        logger.info(f"Data length: {len(historical_data)}")
        logger.info(f"Signals length: {len(strategy_signals)}")
        logger.info(f"Sample signals: {strategy_signals.head()}")  # Debug: Print sample signals

        # Mode-based execution
        if mode == "backtest":
            backtester = Backtester(initial_balance=100, commission=0.01, trade_size=0.5)
            backtest_results = backtester.backtest(historical_data, strategy_signals)
            logger.info(f"📊 Backtest Results: {backtest_results}")

            # Visualize results
            plot_equity_curve(backtest_results['equity_curve'])
            plot_trade_history(historical_data, backtest_results['trades'])

        elif mode == "paper_trade":
            # Initialize paper trader
            paper_trader = PaperTrader()

            # Continuous loop for paper trading
            while not stop_event.is_set():
                try:
                    # Fetch live data
                    live_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME)
                    live_data = pd.DataFrame(live_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    live_data['timestamp'] = pd.to_datetime(live_data['timestamp'], unit='ms')

                    # Preprocess and generate signals
                    live_data = preprocess_data(live_data)
                    signals = strategy.generate_signals(live_data)  # Returns a Series
                    latest_signal = signals.iloc[-1]  # Get the latest signal
                    current_price = live_data['close'].iloc[-1]

                    # Debug: Print live data and signal
                    logger.info(f"Live data: {live_data.tail()}")
                    logger.info(f"Latest signal: {latest_signal}")

                    # Execute trade based on the latest signal
                    await paper_trader.execute_trade(latest_signal, current_price)

                    # Sleep to avoid API rate limits
                    logger.info("🔁 Waiting for the next cycle...")
                    await asyncio.sleep(60)  # Adjust sleep time based on your timeframe

                except Exception as e:
                    logger.error(f"⚠️ Error in paper trading loop: {e}")
                    await asyncio.sleep(10)  # Retry after a short delay

        elif mode == "live_trade":
            # Initialize live trader
            live_trader = LiveTrader(exchange, config.SYMBOL, trading_mode="spot")

            # Continuous loop for live trading
            while not stop_event.is_set():
                try:
                    # Fetch live data
                    live_data = await exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME)
                    live_data = pd.DataFrame(live_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    live_data['timestamp'] = pd.to_datetime(live_data['timestamp'], unit='ms')

                    # Preprocess live data
                    live_data = preprocess_data(live_data)

                    # Generate signals
                    signals = strategy.generate_signals(live_data)  # Returns a Series
                    latest_signal = signals.iloc[-1]  # Get the latest signal
                    current_price = live_data['close'].iloc[-1]

                    # Debug: Print live data and signal
                    logger.info(f"Live data: {live_data.tail()}")
                    logger.info(f"Latest signal: {latest_signal}")

                    # Execute trade
                    await live_trader.execute_trade(latest_signal, current_price, live_data)

                    # Sleep to avoid API rate limits
                    logger.info("🔁 Waiting for the next cycle...")
                    await asyncio.sleep(60)  # Adjust sleep time based on your timeframe

                except Exception as e:
                    logger.error(f"⚠️ Error in live trading loop: {e}")
                    await asyncio.sleep(10)  # Retry after a short delay

        elif mode == "optimize":
            # Define parameter ranges to test
            trade_sizes = [0.05, 0.1, 0.2]  # Test different trade sizes
            commissions = [0.0005, 0.001, 0.002]  # Test different commissions

            # Run optimization
            best_params = optimize_parameters(historical_data, trade_sizes, commissions)
            logger.info(f"🎯 Best Parameters: {best_params}")

    finally:
        # Cancel the exit listener task
        exit_listener.cancel()

        # Close the exchange connection
        await exchange.close()
        logger.info("✅ Exchange connection closed.")

if __name__ == "__main__":
    #asyncio.run(main())
    #asyncio.run(main(mode="backtest"))
    #asyncio.run(main(mode="optimize"))
    #asyncio.run(main(mode="paper_trade"))
    asyncio.run(main(mode="live_trade"))