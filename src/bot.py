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




def set_stop_loss(symbol, current_price, data=None):
    """
    Calculate the stop loss using one of the following methods:
    - Fixed percentage below the current price (default).
    - ATR (Average True Range).
    - Support/Resistance levels.
    """
    if current_price is None:
        logger.warning("❌ Current price is None. Cannot calculate stop loss.")
        return None  # Return None if current_price is not provided

    # Method 1: Fixed percentage below the current price (default)
    stop_loss_percentage = 0.02  # 2%
    stop_loss = current_price * (1 - stop_loss_percentage)

    # Method 2: ATR-based stop loss (uncomment to use)
    # if data is not None and 'ATR' in data.columns:
    #     atr_multiplier = 2  # Example multiplier
    #     atr = data['ATR'].iloc[-1]  # Get the latest ATR value
    #     stop_loss = current_price - (atr * atr_multiplier)
    #     logger.debug(f"Calculated ATR-based stop loss for {symbol}: {stop_loss}")

    # Method 3: Support-based stop loss (uncomment to use)
    # if data is not None and 'Support' in data.columns:
    #     support_level = data['Support'].iloc[-1]  # Get the latest support level
    #     stop_loss = support_level * 0.99  # Set stop loss slightly below support
    #     logger.debug(f"Calculated support-based stop loss for {symbol}: {stop_loss}")

    logger.debug(f"Calculated stop loss for {symbol}: {stop_loss}")
    return stop_loss

last_sent_signal = None  # Store the last sent signal globally

""" &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& """
async def process_signal(signal, symbol, current_price, strategy, data):
    """Processes the trading signal and sends a Telegram notification."""
    global last_sent_signal  # Reference global variable

    try:
        # Construct a unique identifier for the signal (signal type + symbol)
        signal_id = f"{signal}_{symbol}"

        # Avoid sending duplicate signals
        if signal_id == last_sent_signal:
            logger.info(f"⚠️ Duplicate signal '{signal_id}' detected. Skipping Telegram notification.")
            return  # Skip sending duplicate signals

        # Update last sent signal before sending
        last_sent_signal = signal_id

        # Calculate stop-loss and take-profit
        stop_loss = set_stop_loss(symbol, current_price, data)  # Ensure this function is defined
        take_profit = current_price * 1.02  # Example take profit level

        # Format current_price, stop_loss, and take_profit to 2 decimal places
        current_price_str = f"{current_price:.2f}" if current_price is not None else "N/A"
        stop_loss_str = f"{stop_loss:.2f}" if stop_loss is not None else "N/A"
        take_profit_str = f"{take_profit:.2f}" if take_profit is not None else "N/A"

        """ ---------------------------------------------------------------------------------------------------"""


        if signal in ["buy", "sell"]:
            message = f"📢 {signal.upper()} Signal detected! {symbol} at ${current_price_str}\n"
            message += f"📉 Stop Loss: ${stop_loss_str} | 🎯 Take Profit: ${take_profit_str}"
            logger.info(message)
            await send_telegram_message_with_retries(signal, signal=signal_id, pair=symbol, entry_price=current_price_str, stop_loss=stop_loss_str, take_profit=take_profit_str)

        elif signal in ["long", "short"]:
            leverage = 2  # Example leverage value
            message = f"📢 {signal.upper()} Signal detected! {symbol} at ${current_price_str}\n"
            message += f"📉 Stop Loss: ${stop_loss_str} | 🎯 Take Profit: ${take_profit_str} | 🔝 Leverage: {leverage}x"
            logger.info(message)
            await send_telegram_message_with_retries(signal, signal=signal_id, pair=symbol, leverage=leverage, entry_price=current_price_str, stop_loss=stop_loss_str, take_profit=take_profit_str)


            
        elif signal == "neutral":
            # Extract the indicator values
            rsi = data['RSI'].iloc[-1] if 'RSI' in data.columns and data['RSI'].iloc[-1] is not None else None
            macd = data['MACD'].iloc[-1] if 'MACD' in data.columns and data['MACD'].iloc[-1] is not None else None
            bollinger_upper = data['Upper_Band'].iloc[-1] if 'Upper_Band' in data.columns and data['Upper_Band'].iloc[-1] is not None else None
            bollinger_lower = data['Lower_Band'].iloc[-1] if 'Lower_Band' in data.columns and data['Lower_Band'].iloc[-1] is not None else None

            # Safely format indicator values, checking for None
            rsi_str = f"{rsi:.2f}" if isinstance(rsi, (float, int)) else "N/A"
            macd_str = f"{macd:.2f}" if isinstance(macd, (float, int)) else "N/A"
            bollinger_upper_str = f"{bollinger_upper:.2f}" if isinstance(bollinger_upper, (float, int)) else "N/A"
            bollinger_lower_str = f"{bollinger_lower:.2f}" if isinstance(bollinger_lower, (float, int)) else "N/A"

            """ ---------------------------------------------------------------------------------------------------"""

            # Log the message with the formatted indicator values
            message = f"⚖️ Neutral signal detected for {symbol} at ${current_price_str}.\n"
            message += f"🔹 RSI: {rsi_str}\n"
            message += f"🔹 MACD: {macd_str}\n"
            message += f"🔹 Bollinger Bands: Upper={bollinger_upper_str}, Lower={bollinger_lower_str}\n"
            message += "🔹 Market conditions are unclear.\n"
            message += "🔹 Recommendation: Hold current position or reduce exposure."
            logger.info(message)
            await send_telegram_message_with_retries("neutral", signal=signal_id, pair=symbol, current_price=current_price_str, rsi=rsi_str, macd=macd_str, bollinger_upper=bollinger_upper_str, bollinger_lower=bollinger_lower_str)
            
            
            """ ---------------------------------------------------------------------------------------------------"""
        
        elif signal == "strong_buy":
            analysis = "Strong buy opportunity detected"
            message = f"🚀 Strong Buy Signal detected! {symbol} at ${current_price_str}\n"
            message += f"📉 Stop Loss: ${stop_loss_str} | 🎯 Take Profit: ${take_profit_str}"
            logger.info(message)
            await send_telegram_message_with_retries("strong_buy", signal=signal_id, pair=symbol, current_price=current_price_str, stop_loss=stop_loss_str, take_profit=take_profit_str, analysis=analysis)

            """ ---------------------------------------------------------------------------------------------------"""

        elif signal == "strong_sell":
            analysis = "Strong sell opportunity detected"
            message = f"⚠️ Strong Sell Signal detected! {symbol} at ${current_price_str}\n"
            message += f"📉 Stop Loss: ${stop_loss_str} | 🎯 Take Profit: ${take_profit_str}"
            logger.info(message)
            await send_telegram_message_with_retries("strong_sell", signal=signal_id, pair=symbol, current_price=current_price_str, stop_loss=stop_loss_str, take_profit=take_profit_str, analysis=analysis)

        else:
            logger.warning(f"❌ Unknown signal received: {signal}")
            await send_telegram_message_with_retries("error", error="An unknown signal was received.")

    except Exception as e:
        logger.error(f"❌ Error processing signal: {e}\n{traceback.format_exc()}")
        await send_telegram_message_with_retries("error", error=f"Error processing signal: {e}")

""" &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& """

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
    #syncio.run(main(mode="backtest"))
    asyncio.run(main(mode="optimize"))
    #asyncio.run(main(mode="paper_trade"))
    #asyncio.run(main(mode="live_trade"))