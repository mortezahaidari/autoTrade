import logging
import pandas as pd
from strategies.bollinger_band_strategy import BollingerBandsStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.moving_average_crossover_strategy import MovingAverageCrossoverStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.stochastic_oscillator import StochasticOscillatorStrategy

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CombinedStrategy:
    def __init__(self):
        # Initialize strategies
        self.rsi = RSIStrategy()
        self.macd = MACDStrategy()
        self.bollinger = BollingerBandsStrategy()
        self.sma = SMACrossoverStrategy()
        self.stochastic = StochasticOscillatorStrategy()
        self.moving_average_cross = MovingAverageCrossoverStrategy()

        # Signal history for additional confirmation
        self.signal_history = []

        # Weights for signals
        self.weight_map = {
            'strong_buy': 3,
            'buy': 2,
            'neutral': 0,
            'sell': -2,
            'strong_sell': -3
        }

        # Threshold for strong signals
        self.strong_signal_threshold = 3  # Increase from 2 to reduce false signals
        self.history_length = 5  # Consider last 5 signals instead of 3 for trend confirmation

    def generate_signals(self, data):
        """
        Generates time-varying trading signals for the given data.
        
        Args:
            data (pd.DataFrame): Historical or live OHLCV data.
        
        Returns:
            pd.Series: Trading signals for each row in the data (e.g., 'buy', 'sell', 'neutral').
        """
        # Generate signals from all strategies
        strategies = {
            'RSI': self.rsi,
            'MACD': self.macd,
            'Bollinger Bands': self.bollinger,
            'SMA Crossover': self.sma,
            'Stochastic Oscillator': self.stochastic,
            'Moving Average Crossover': self.moving_average_cross
        }

        # Initialize a DataFrame to store signals from all strategies
        signals_df = pd.DataFrame(index=data.index)

        for name, strategy in strategies.items():
            try:
                # Generate signals for the current strategy
                signals = strategy.generate_signals(data)
                signals_df[name] = signals
            except Exception as e:
                logger.error(f"❌ Error generating signal from {name}: {e}")
                signals_df[name] = 'neutral'  # Default to 'neutral' if an error occurs

        # Log individual signals
        logger.info(f"📊 Individual Signals:\n{signals_df.tail()}")

        # Assign weights to the signals
        weighted_signals = signals_df.applymap(lambda x: self.weight_map.get(x, 0))  # Map signals to weights
        total_weights = weighted_signals.sum(axis=1)  # Sum weights for each row

        # Log the weighted counts
        logger.info(f"📉 Weighted Signal Count:\n{weighted_signals.tail()}")
        logger.info(f"📊 Total Weights:\n{total_weights.tail()}")

        # Determine final signal for each row based on weight threshold
        final_signals = []
        for weight in total_weights:
            if weight >= self.strong_signal_threshold:
                final_signal = 'strong_buy'
            elif weight <= -self.strong_signal_threshold:
                final_signal = 'strong_sell'
            else:
                # Store recent weights for trend analysis
                self.signal_history.append(weight)
                if len(self.signal_history) > self.history_length:
                    self.signal_history.pop(0)  # Keep only the last `history_length` weights

                # Check if the recent trend favors buying or selling
                positive_trend = sum(1 for w in self.signal_history if w > 0) > len(self.signal_history) / 2
                negative_trend = sum(1 for w in self.signal_history if w < 0) > len(self.signal_history) / 2

                if positive_trend:
                    final_signal = 'buy'
                elif negative_trend:
                    final_signal = 'sell'
                else:
                    final_signal = 'neutral'

            final_signals.append(final_signal)

        # Log the final signals
        logger.info(f"✅ Combined Strategy Decision:\n{pd.Series(final_signals, index=data.index).tail()}")

        return pd.Series(final_signals, index=data.index)