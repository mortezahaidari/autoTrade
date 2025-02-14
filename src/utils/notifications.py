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