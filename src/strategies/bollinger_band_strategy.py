import logging

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class BollingerBandsStrategy:
    def __init__(self, period=20, std_dev=2):
        self.period = period
        self.std_dev = std_dev
        

    def generate_signals(self, data):
        
        if "close" not in data.columns:
            return None

        # Calculate Bollinger Bands
        data['SMA'] = data['close'].rolling(window=self.period).mean()
        data['StdDev'] = data['close'].rolling(window=self.period).std()
        data['UpperBand'] = data['SMA'] + (self.std_dev * data['StdDev'])
        data['LowerBand'] = data['SMA'] - (self.std_dev * data['StdDev'])

        # Log only the price, bands, and signal
        latest_close = data['close'].iloc[-1]
        latest_upper_band = data['UpperBand'].iloc[-1]
        latest_lower_band = data['LowerBand'].iloc[-1]
        if latest_close < latest_lower_band:
            logger.info(f"✅ Bollinger Bands Strategy: Strong Buy Signal (Price={latest_close:.2f}, Lower Band={latest_lower_band:.2f})")
            return 'strong_buy'
        elif latest_close > latest_upper_band:
            logger.info(f"✅ Bollinger Bands Strategy: Strong Sell Signal (Price={latest_close:.2f}, Upper Band={latest_upper_band:.2f})")
            return 'strong_sell'
        else:
            logger.info(f"✅ Bollinger Bands Strategy: Neutral Signal (Price={latest_close:.2f}, Upper Band={latest_upper_band:.2f}, Lower Band={latest_lower_band:.2f})")
            return 'neutral'