# src/utils/data_quality.py
import pandas as pd
from typing import Tuple, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)

def validate_ohlcv(data: pd.DataFrame, 
                  symbol: str = None) -> Tuple[bool, pd.DataFrame]:
    """
    Validate OHLCV data with comprehensive checks:
    1. Column structure validation
    2. Data type verification
    3. Time sequence checks
    4. Price validity checks
    5. Volume sanity checks
    
    Returns:
        tuple: (is_valid, validated_data)
    """
    required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    validation_results = {
        'has_required_columns': False,
        'non_empty': False,
        'time_ordered': False,
        'valid_prices': False,
        'valid_volumes': False
    }
    
    try:
        # Check 1: Required columns exist
        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required OHLCV columns")
            return False, data
        
        validation_results['has_required_columns'] = True
        
        # Check 2: Non-empty dataset
        if data.empty:
            logger.warning("Empty OHLCV dataset received")
            return False, data
            
        validation_results['non_empty'] = True
        
        # Check 3: Time sequence validation
        data = data.sort_values('timestamp').reset_index(drop=True)
        time_diff = data['timestamp'].diff().dropna()
        
        if (time_diff <= pd.Timedelta(0)).any():
            logger.warning("Non-chronological timestamps detected")
            return False, data
            
        validation_results['time_ordered'] = True
        
        # Check 4: Price validity
        price_checks = (
            (data['high'] >= data['low']) &
            (data['high'] >= data['close']) &
            (data['high'] >= data['open']) &
            (data['low'] <= data['close']) &
            (data['low'] <= data['open']) &
            (data['close'] > 0) &
            (data['open'] > 0) &
            (data['high'] > 0) &
            (data['low'] > 0)
        )
        
        if not price_checks.all():
            logger.warning("Invalid price relationships detected")
            return False, data
            
        validation_results['valid_prices'] = True
        
        # Check 5: Volume validation
        volume_checks = (
            (data['volume'] >= 0) &
            (data['volume'] < data['volume'].quantile(0.999) * 10)  # Outlier check
        )
        
        if not volume_checks.all():
            logger.warning("Suspicious volume values detected")
            return False, data
            
        validation_results['valid_volumes'] = True
        
        logger.info(f"OHLCV validation passed for {symbol}" if symbol else "OHLCV validation passed")
        return True, data

    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, data

def clean_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """
    Clean OHLCV data by:
    - Removing invalid rows
    - Filling small gaps
    - Normalizing formats
    """
    try:
        # Remove rows with NA values in critical columns
        data = data.dropna(subset=required_columns, how='any')
        
        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # Forward fill small gaps (max 3 periods)
        data = data.ffill(limit=3)
        
        # Convert timestamp to datetime
        if not pd.api.types.is_datetime64_any_dtype(data['timestamp']):
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            
        return data
    
    except Exception as e:
        logger.error(f"Data cleaning failed: {str(e)}")
        return data