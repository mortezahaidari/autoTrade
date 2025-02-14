import pandas as pd
import numpy as np


import pandas as pd
import numpy as np

def preprocess_data(df):
    """Generates and scales features for ML models."""
    # Ensure the timestamp column exists
    if 'timestamp' not in df.columns:
        if 'time' in df.columns:  # Check for alternative column names
            df.rename(columns={'time': 'timestamp'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'timestamp'}, inplace=True)
        else:
            raise KeyError("DataFrame must contain a 'timestamp' column or equivalent.")

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # Assuming timestamp is in milliseconds
    df = df.set_index('timestamp')

    # Moving Averages
    df['Short_MA'] = df['close'].rolling(window=50, min_periods=1).mean()
    df['Long_MA'] = df['close'].rolling(window=200, min_periods=1).mean()

    # RSI
    df['RSI'] = compute_rsi(df)

    # Bollinger Bands
    df['Rolling_Std'] = df['close'].rolling(window=20, min_periods=1).std()
    df['Upper_Band'] = df['Short_MA'] + (2 * df['Rolling_Std'])
    df['Lower_Band'] = df['Short_MA'] - (2 * df['Rolling_Std'])

    # MACD
    df['Short_EMA'] = df['close'].ewm(span=12, adjust=False).mean()
    df['Long_EMA'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['Short_EMA'] - df['Long_EMA']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Stochastic Oscillator
    df['Lowest_Low'] = df['low'].rolling(window=14, min_periods=1).min()
    df['Highest_High'] = df['high'].rolling(window=14, min_periods=1).max()
    df['%K'] = 100 * ((df['close'] - df['Lowest_Low']) / (df['Highest_High'] - df['Lowest_Low']))
    df['%D'] = df['%K'].rolling(window=3, min_periods=1).mean()
    
    # VWAP (Volume Weighted Average Price)
    df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    
    # ATR (Average True Range)
    df['High_Low'] = df['high'] - df['low']
    df['High_Close'] = np.abs(df['high'] - df['close'].shift())
    df['Low_Close'] = np.abs(df['low'] - df['close'].shift())
    df['True_Range'] = df[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
    df['ATR'] = df['True_Range'].rolling(window=14, min_periods=1).mean()
    
    # Ichimoku Cloud
    df['Tenkan_Sen'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2
    df['Kijun_Sen'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
    df['Senkou_Span_A'] = ((df['Tenkan_Sen'] + df['Kijun_Sen']) / 2).shift(26)
    df['Senkou_Span_B'] = ((df['high'].rolling(window=52).max() + df['low'].rolling(window=52).min()) / 2).shift(26)
    df['Chikou_Span'] = df['close'].shift(-26)
    
    # Parabolic SAR
    df['PSAR'] = compute_parabolic_sar(df)
    
    # ADX (Average Directional Index)
    df['ADX'] = compute_adx(df)
    
    # Fill missing values to maintain length consistency
    df.fillna(method='ffill', inplace=True)
    df.fillna(method='bfill', inplace=True)
    return df


def compute_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_parabolic_sar(df):
    """Calculates Parabolic SAR (Simplified version)."""
    psar = df['close'].rolling(window=5, min_periods=1).mean()  # Placeholder formula
    return psar

def compute_adx(df, period=14):
    """Calculates ADX (Average Directional Index)."""
    df['DM+'] = np.where((df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']), df['high'] - df['high'].shift(1), 0)
    df['DM-'] = np.where((df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)), df['low'].shift(1) - df['low'], 0)
    df['TR'] = df[['high', 'low', 'close']].max(axis=1) - df[['high', 'low', 'close']].min(axis=1)
    df['DI+'] = 100 * (df['DM+'].rolling(window=period).mean() / df['TR'].rolling(window=period).mean())
    df['DI-'] = 100 * (df['DM-'].rolling(window=period).mean() / df['TR'].rolling(window=period).mean())
    df['DX'] = 100 * (np.abs(df['DI+'] - df['DI-']) / (df['DI+'] + df['DI-']))
    adx = df['DX'].rolling(window=period).mean()
    return adx
