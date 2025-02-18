# exchange.py
import ccxt.async_support as ccxt
import pandas as pd
import logging
import asyncio
import sys
import aiohttp
from tenacity import *
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Any
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# =====================
# Exception Classes
# =====================
class ExchangeError(Exception):
    """Base exception for all exchange-related errors"""
    pass

class DataValidationError(ExchangeError):
    """Raised when data validation fails"""
    pass

class CircuitBreakerOpen(ExchangeError):
    """Raised when circuit breaker is active"""
    pass

# =====================
# Data Classes
# =====================
@dataclass
class ExchangeConfig:
    """Central configuration for exchange behavior"""
    max_retries: int = 3
    retry_delay: float = 2.0
    slippage: float = 0.001  # 0.1% default slippage
    fee_rate: float = 0.001  # 0.1% default fee
    min_margin_level: float = 1.2
    sync_interval: int = 300  # 5 minutes
    circuit_breaker_threshold: int = 5

@dataclass
class OrderParams:
    """Container for validated order parameters"""
    amount: float    # Executable amount after adjustments
    price: float     # Slippage-adjusted price
    fee: float       # Calculated fee amount
    original_amount: float  # Requested amount before adjustments

# =====================
# Circuit Breaker
# =====================
class CircuitBreaker:
    """Protects against repeated API failures"""
    
    def __init__(self, threshold: int):
        self.failure_count = 0
        self.threshold = threshold
        self.state = "CLOSED"

    def record_failure(self):
        """Track failures and update state"""
        self.failure_count += 1
        if self.failure_count >= self.threshold:
            self.state = "OPEN"
            logger.critical("API circuit breaker opened!")

    def is_open(self):
        """Check if circuit breaker is active"""
        return self.state == "OPEN"

# =====================
# Base Exchange Class
# =====================
class BaseExchange:
    """Core exchange functionality with safety features"""
    
    def __init__(self, api_key: str, api_secret: str, trading_mode: str = "spot", config: ExchangeConfig = ExchangeConfig()):
        self.api_key = api_key
        self.api_secret = api_secret
        self.trading_mode = trading_mode  # Accept trading_mode parameter
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.exchange: Optional[ccxt.Exchange] = None
        self.circuit_breaker = CircuitBreaker(config.circuit_breaker_threshold)
        self._last_sync = 0

    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, *exc_info):
        """Context manager exit"""
        await self.close()

    async def initialize(self):
        """Initialize exchange connection"""
        if self.circuit_breaker.is_open():
            raise CircuitBreakerOpen("API access suspended")
            
        self.session = aiohttp.ClientSession()
        self.exchange = ccxt.binance({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "session": self.session,
            'options': {
                'adjustForTimeDifference': False,
                'defaultType': self.trading_mode,  # Use trading_mode here
            },
        })
        await self.sync_time(force=True)

    async def close(self):
        """Cleanup resources"""
        if self.exchange:
            await self.exchange.close()
        if self.session:
            await self.session.close()

    async def sync_time(self, force: bool = False):
        """Synchronize exchange timestamps"""
        if force or (time.time() - self._last_sync) > self.config.sync_interval:
            try:
                server_time = await self.exchange.public_get_time()
                self.exchange.options['timestamp'] = server_time['serverTime']
                self._last_sync = time.time()
            except Exception as e:
                logger.error(f"Time sync failed: {str(e)}")

# =====================
# Spot Trading
# =====================
class BinanceSpot(BaseExchange):
    """Binance Spot Trading Implementation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exchange.options['defaultType'] = 'spot'

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def place_order(self, symbol: str, side: str, amount: float, 
                        order_type: str = 'market', params: dict = None) -> dict:
        """
        Execute spot order with:
        - Automatic slippage adjustment
        - Fee calculations
        - Circuit breaker protection
        """
        try:
            params = params or {}
            if self.circuit_breaker.is_open():
                raise CircuitBreakerOpen()

            # Calculate order parameters
            order_params = await self._calculate_order_params(symbol, side, amount)
            
            # Execute order
            return await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=order_params.amount,
                price=order_params.price,
                params=params
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Spot order failed: {str(e)}")
            raise

    async def _calculate_order_params(self, symbol: str, side: str, amount: float) -> OrderParams:
        """Calculate fees, slippage, and validate amounts"""
        ticker = await self.exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # Calculate adjusted price with slippage
        slippage_price = current_price * (1 + self.config.slippage * (1 if side == 'buy' else -1))
        
        # Calculate fees
        fee = amount * slippage_price * self.config.fee_rate
        
        # Adjust amount for fees
        adjusted_amount = amount - (fee / slippage_price)
        
        return OrderParams(
            amount=adjusted_amount,
            price=slippage_price,
            fee=fee,
            original_amount=amount
        )

# =====================
# Margin Trading
# =====================
class BinanceMargin(BinanceSpot):
    """Binance Margin Trading Implementation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exchange.options['defaultType'] = 'margin'

    async def place_order(self, symbol: str, side: str, amount: float, 
                        order_type: str = 'market', params: dict = None) -> dict:
        """Margin order with risk checks"""
        try:
            if not await self._check_margin_health(symbol, side, amount):
                raise ExchangeError("Margin requirements not met")
                
            return await super().place_order(symbol, side, amount, order_type, params)
        except Exception as e:
            logger.error(f"Margin order failed: {str(e)}")
            raise

    async def _check_margin_health(self, symbol: str, side: str, amount: float) -> bool:
        """Verify margin account health"""
        margin_account = await self.exchange.fetch_balance()
        margin_level = float(margin_account.get('marginLevel', 0))
        return margin_level >= self.config.min_margin_level

# =====================
# Advanced Features
# =====================
class AdvancedExchange(BinanceMargin):
    """Unified exchange interface with enhanced features"""
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, 
                        limit: int = 100, params: dict = None) -> pd.DataFrame:
        """Fetch and validate OHLCV data"""
        try:
            await self.sync_time()
            data = await self.exchange.fetch_ohlcv(symbol, timeframe, limit, params)
            return self._validate_ohlcv(data)
        except Exception as e:
            logger.error(f"OHLCV fetch failed: {str(e)}")
            return pd.DataFrame()

    def _validate_ohlcv(self, data: pd.DataFrame) -> pd.DataFrame:
        """Ensure data quality standards"""
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required):
            raise DataValidationError("Invalid OHLCV structure")
        return data.dropna().reset_index(drop=True)

# =====================
# Legacy Compatibility
# =====================
class Exchange(AdvancedExchange):
    """Maintains original interface for backward compatibility"""
    
    async def place_market_order(self, symbol: str, side: str, amount: float) -> dict:
        """Legacy market order interface"""
        if self.exchange is None:
            raise ExchangeError("Exchange instance is not available (closed)")
        return await self.place_order(symbol, side, amount, 'market')

    async def place_margin_order(self, symbol: str, side: str, amount: float) -> dict:
        """Legacy margin order interface"""
        if self.exchange is None:
            raise ExchangeError("Exchange instance is not available (closed)")
        return await self.place_order(
            symbol, side, amount, 'market', 
            {'marginMode': 'cross'}
        )

    async def fetch_balance(self) -> dict:
        """Legacy balance check"""
        return await self.exchange.fetch_balance()
