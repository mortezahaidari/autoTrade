import os
import logging
import aiohttp
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Define retry parameters
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

last_sent_signal = None  # Store last sent signal

# Define message templates
# Define message templates
MARKET_ORDER_MESSAGES = {
    "buy": "📈 *Market Buy Order Executed\!* \n🔹 Pair: `{pair}`\n🔹 Order Type: `Market`\n🔹 Entry: `{entry_price}`\n🔹 Stop\-Loss: `{stop_loss}`\n🔹 Take\-Profit: `{take_profit}`",
    "sell": "📉 *Market Sell Order Executed\!* \n🔹 Pair: `{pair}`\n🔹 Order Type: `Market`\n🔹 Entry: `{entry_price}`\n🔹 Stop\-Loss: `{stop_loss}`\n🔹 Take\-Profit: `{take_profit}`",
}

MARGIN_ORDER_MESSAGES = {
    "long": "🔥 *Margin Long Position Opened\!* \n🔹 Pair: `{pair}`\n🔹 Leverage: `{leverage}x`\n🔹 Entry: `{entry_price}`\n🔹 Stop\-Loss: `{stop_loss}`\n🔹 Take\-Profit: `{take_profit}`",
    "short": "🧊 *Margin Short Position Opened\!* \n🔹 Pair: `{pair}`\n🔹 Leverage: `{leverage}x`\n🔹 Entry: `{entry_price}`\n🔹 Stop\-Loss: `{stop_loss}`\n🔹 Take\-Profit: `{take_profit}`",
}

TECHNICAL_SIGNAL_MESSAGES = {
    "macd": "📊 *MACD Signal Detected\!* \n🔹 Pair: `{pair}`\n🔹 MACD Crossover: `{signal_type}`\n🔹 Recommendation: `{recommendation}`",
    "sma_crossover": "📊 *SMA Crossover Signal\!* \n🔹 Pair: `{pair}`\n🔹 Fast SMA: `{fast_sma}`\n🔹 Slow SMA: `{slow_sma}`\n🔹 Trend: `{trend}`",
    "stochastic": "📊 *Stochastic Oscillator Alert\!* \n🔹 Pair: `{pair}`\n🔹 Overbought/Oversold: `{stochastic_level}`\n🔹 Recommendation: `{recommendation}`",
    "rsi": "📊 *RSI Alert\!* \n🔹 Pair: `{pair}`\n🔹 RSI Value: `{rsi_value}`\n🔹 Condition: `{rsi_condition}`\n🔹 Recommendation: `{recommendation}`",
    "neutral": "⚖️ *Neutral Signal Detected\!* \n🔹 Pair: `{pair}`\n🔹 Current Price: `{current_price}`\n🔹 RSI: `{rsi}`\n🔹 MACD: `{macd}`\n🔹 Bollinger Bands: Upper\=`{bollinger_upper}`, Lower\=`{bollinger_lower}`\n🔹 Market conditions are unclear\.\n🔹 Recommendation: `{recommendation}`",
    "strong_buy": "🚀 *Strong Buy Signal\!* \n🔹 Pair: `{pair}`\n🔹 Price: `{current_price}`\n🔹 Analysis: `{analysis}`",
    "strong_sell": "⚠️ *Strong Sell Signal\!* \n🔹 Pair: `{pair}`\n🔹 Price: `{current_price}`\n🔹 Analysis: `{analysis}`",
}

MARGIN_CALL_ALERT = "⚠️ *Margin Call Warning\!* \n🔹 Pair: `{pair}`\n🔹 Current Price: `{current_price}`\n🔹 Liquidation Price: `{liquidation_price}`\n🔹 Leverage: `{leverage}x`\n🔹 Suggested Action: `{action}`"

ERROR_MESSAGE = "❌ *Error in AutoTrade Bot:* `{error}`"

def escape_markdown(text):
    """Escape MarkdownV2 special characters for Telegram messages."""
    reserved_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in reserved_chars:
        text = str(text).replace(char, f'\\{char}')
    return text

async def send_telegram_message(order_type, **kwargs):
    """Send structured market, margin order, or strategy signals to Telegram."""
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not telegram_bot_token or not telegram_chat_id:
        logger.error("❌ Telegram bot token or chat ID is not set.")
        return

    # Determine message category
    if order_type in MARKET_ORDER_MESSAGES:
        message_template = MARKET_ORDER_MESSAGES[order_type]
    elif order_type in MARGIN_ORDER_MESSAGES:
        message_template = MARGIN_ORDER_MESSAGES[order_type]
    elif order_type in TECHNICAL_SIGNAL_MESSAGES:
        message_template = TECHNICAL_SIGNAL_MESSAGES[order_type]
    elif order_type == "margin_call":
        message_template = MARGIN_CALL_ALERT
    elif order_type == "error":
        message_template = ERROR_MESSAGE
    else:
        logger.error(f"⚠️ Unknown order type: {order_type}")
        return

    # Format the message and escape Markdown characters
    escaped_kwargs = {k: escape_markdown(v) for k, v in kwargs.items()}
    message = message_template.format(**escaped_kwargs)

    # Telegram API URL
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message, "parse_mode": "MarkdownV2"}

    logger.info("📤 Sending Telegram message...")

    # Retry logic with exponential backoff
    for i in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 404:
                        logger.error(f"❌ Not Found: Check your bot token and chat ID.")
                    response.raise_for_status()
                    logger.info("✅ Telegram message sent successfully.")
                    return
        except aiohttp.ClientError as e:
            delay = RETRY_DELAY * (2 ** i)
            logger.error(f"❌ Failed to send Telegram notification (attempt {i + 1}/{MAX_RETRIES}): {e}")
            if i < MAX_RETRIES - 1:
                logger.info(f"⏳ Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error("❌ Max retries reached. Failed to send Telegram notification.")
                return
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return
        
        
async def send_telegram_message_with_retries(order_type, **kwargs):
    """Send a Telegram message with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await send_telegram_message(order_type, **kwargs)
            return
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram notification (attempt {attempt}/{MAX_RETRIES}): {e}")
            await asyncio.sleep(RETRY_DELAY)
    logger.error("❌ Failed to send Telegram notification after multiple attempts.")

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