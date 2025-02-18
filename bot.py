import asyncio
import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Optional, Any

from core.execution.exchange import Exchange
from strategies.strategy_factory import StrategyFactory, StrategyConfig, StrategyParameters  # Added StrategyConfig import
from core.execution.live_trader import LiveTrader
from core.analysis.metrics import TradeAnalyzer
from ml.models.model_training import MLTraining
import joblib
from core.config import settings


# Enhanced imports
from prometheus_client import start_http_server, Counter, Gauge
from core.utilities.data_quality import validate_ohlcv, clean_ohlcv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    """Enhanced trading bot with ML integration and advanced monitoring"""
    
    def __init__(self):
        self.stop_event = asyncio.Event()
        self.analyzer = TradeAnalyzer()
        self.ml_model: Optional[MLTraining] = None
        self.exchange: Optional[Exchange] = None
        self.strategy = self._create_strategy()  # Use validated strategy creation
        self._init_metrics()


    def _load_strategy_config(self) -> StrategyConfig:
        raw_config = settings.STRATEGY_CONFIG
        
        dependencies = {}
        for dep_name, dep_config in raw_config.get("dependencies", {}).items():
            # Get proper parameters class for each dependency
            strategy_class, param_model = StrategyFactory.get_strategy_type(
                dep_config["name"], 
                dep_config.get("version", "1.0.0")
            )
            dependencies[dep_name] = StrategyConfig(
                name=dep_config["name"],
                parameters=param_model(**dep_config["parameters"]),
                version=dep_config.get("version", "1.0.0")
            )
        
        # Get main strategy parameters class
        main_strategy_class, main_param_model = StrategyFactory.get_strategy_type(
            raw_config["name"],
            raw_config.get("version", "1.0.0")
        )
        
        return StrategyConfig(
            name=raw_config["name"],
            parameters=main_param_model(**raw_config["parameters"]),
            dependencies=dependencies,
            version=raw_config.get("version", "1.0.0")
        )

    
    
    
    def _validate_dependencies(self, deps: Dict[str, StrategyConfig]) -> Dict[str, StrategyConfig]:
        """ Validate enabled status and configuration of strategy dependencies """
        if not deps:
            return deps
        for dep_name, config in deps.items():
            if not config.enabled:
                raise ValueError(f"Dependency strategy '{dep_name}' is disabled")
            if not StrategyFactory.is_strategy_registered(config.name, config.version):
                raise ValueError(f"Unregistered dependenciy: {config.name}@{config.version}")
            
        return deps    


    def _create_strategy(self) -> Any:
        """Create strategy instance with validation"""
        try:
            strategy_config = self._load_strategy_config()
            return StrategyFactory.create_strategy(strategy_config)
        except ValueError as e:
            logger.critical(f"Strategy creation failed: {e}")
            raise SystemExit(1) from e



    def _init_metrics(self):
        """Initialize monitoring metrics"""
        # Trade metrics
        self.trades_total = Counter(
            'trades_total', 
            'Total trades by strategy and symbol', 
            ['strategy', 'symbol']
        )
        self.trades_by_side = Counter(
            'trades_by_side',
            'Trades by symbol and side',
            ['symbol', 'side']
        )
        
        # Strategy performance metrics
        self.buy_signals = Gauge(
            'strategy_buy_signals',
            'Buy signals count',
            ['timeframe']
        )
        self.sell_signals = Gauge(
            'strategy_sell_signals',
            'Sell signals count',
            ['timeframe']
        )
        
        # System metrics
        self.latency_gauge = Gauge('api_latency', 'API call latency in ms')

        if settings.METRICS_ENABLED:
            start_http_server(settings.METRICS_PORT)

    async def initialize(self):
        """Initialize exchange connection and ML model"""
        self._validate_strategy_dependencies()

        # Add strategy registration check
        if not StrategyFactory.is_strategy_registered("atr_filter", "1.2.0"):
            raise RuntimeError("ATR Filter strategy not registered")
        
        load_dotenv()
        
        async with Exchange(
            os.getenv("BINANCE_API_KEY"),
            os.getenv("BINANCE_API_SECRET"),
            trading_mode=settings.TRADING_MODE
        ) as self.exchange:
            await self._initialize_ml_model()
            await self._main_loop()

    def _validate_strategy_dependencies(self):
        """Ensure all required strategies are registered"""
        required = [
            (cfg['name'], cfg.get('version', '1.0.0'))
            for cfg in settings.STRATEGY_CONFIG.get('dependencies', {}).values()
        ]
        
        for name, version in required:
            if not StrategyFactory.is_strategy_registered(name, version):
                raise RuntimeError(f"Unregistered dependency: {name}@{version}")        

    async def _initialize_ml_model(self):
        """ML model initialization with fallback"""
        if self.ml_model and self.ml_model.is_loaded:
            return # Skip reinitialization
        
        try:
            self.ml_model = MLTraining()
            if not self.ml_model.load_model():
                if settings.AUTO_RETRAIN:
                    await self._retrain_model()
                else:
                    raise RuntimeError("ML model unavailable")
        except Exception as e:
            logger.error(f"ML initialization failed: {str(e)}")
            if settings.REQUIRE_ML:
                raise

    async def _retrain_model(self):
        """Automated model retraining pipeline"""
        logger.info("Initiating model retraining...")
        data = await self._fetch_training_data()
        if not data.empty:
            self.ml_model.train_model(data)
            logger.info(f"New model version {self.ml_model.version} deployed")

    async def _fetch_training_data(self) -> pd.DataFrame:
        """Fetch validated training data"""
        raw_data = await self.exchange.fetch_ohlcv(
            settings.SYMBOL,
            settings.MODEL_TIMEFRAME,
            limit=settings.MODEL_TRAINING_WINDOW
        )

        df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        is_valid, validated_df = validate_ohlcv(df, settings.SYMBOL)
        if not is_valid:
            logger.error("❌ Invalid training data - aborting model training")
            return pd.DataFrame()
        
        return clean_ohlcv(validated_df)

    async def _main_loop(self):
        """Enhanced main trading loop with circuit breaker"""
        last_balance_check = datetime.now()
        
        while not self.stop_event.is_set():
            try:
                if self.exchange.circuit_breaker.is_open():
                    logger.critical("Circuit breaker tripped!")
                    break

                analysis = await self._analyze_markets()
                
                if (datetime.now() - last_balance_check) > timedelta(minutes=30):
                    await self.exchange.fetch_balance()
                    last_balance_check = datetime.now()
                
                if self._should_execute(analysis):
                    await self._execute_trade(analysis)
                
                if self.ml_model and self.ml_model.check_drift(analysis[settings.PRIMARY_TIMEFRAME]['data']):
                    logger.warning("Model drift detected!")
                    await self._retrain_model()

                await asyncio.sleep(settings.LOOP_INTERVAL)
                
            except Exception as e:
                logger.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(settings.ERROR_RETRY_DELAY)

    async def _analyze_markets(self) -> Dict:
        """Multi-timeframe market analysis"""
        analysis = {}
        for tf in settings.TIMEFRAMES:
            try:
                with self.latency_gauge.time():
                    raw_data = await self.exchange.fetch_ohlcv(settings.SYMBOL, tf)
            
                df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                is_valid, validated_df = validate_ohlcv(df, settings.SYMBOL)
                if df.empty:
                    logger.warning(f"No data for {tf}")
                    continue

                if not is_valid:
                    logger.warning(f"⚠️ Invalid {tf} data - skipping timeframe")
                    continue
                    
                cleaned_data = clean_ohlcv(validated_df)
                signals = self.strategy.generate_signals(cleaned_data)

                self._track_strategy_metrics(tf, signals)

                analysis[tf] = {
                    'data': cleaned_data,
                    'signal': signals,
                    'ml_confidence': self.ml_model.predict_confidence(cleaned_data) if self.ml_model else None
                }

            except Exception as e:
                logger.error(f"Error processing {tf} data: {str(e)}")
                continue
    
        return analysis

    def _track_strategy_metrics(self, timeframe: str, signals: pd.Series) -> None:
        """Record strategy performance metrics"""
        buy_signals = sum(signals == 'buy') if signals is not None else 0
        sell_signals = sum(signals == 'sell') if signals is not None else 0
        
        self.buy_signals.labels(timeframe=timeframe).set(buy_signals)
        self.sell_signals.labels(timeframe=timeframe).set(sell_signals)

    def _should_execute(self, analysis: Dict) -> bool:
        """Trade signal validation with multiple checks"""
        primary = analysis[settings.PRIMARY_TIMEFRAME]
        return (
            primary['signal'] != 'hold' and
            (not self.ml_model or primary['ml_confidence'] >= settings.MIN_CONFIDENCE) and
            self.analyzer.acceptable_volatility(primary['data'])
        )

    async def _execute_trade(self, analysis: Dict):
        """Execute trade with risk management"""
        primary = analysis[settings.PRIMARY_TIMEFRAME]
        symbol = settings.SYMBOL
        signal = primary['signal'].lower()
        
        try:
            size = await self._calculate_position_size(signal)
            if size <= 0:
                return

            result = await self.exchange.place_order(
                symbol=symbol,
                side=signal,
                amount=size,
                order_type='market',
                params={'test': settings.DRY_RUN, 'strategy': settings.STRATEGY_CONFIG['name']}
            )
        
            if result:
                self._record_trade_execution(result, primary)
                self.trades_by_side.labels(symbol=symbol, side=signal).inc()
                self.analyzer.record_trade(result)
                logger.info(f"Executed {signal} order for {size} {symbol}")

        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}", exc_info=True) # added stacktrace
            self._log_strategy_error(primary['data'])        

    def _record_trade_execution(self, result: dict, analysis: dict):
        """Record trade execution details"""
        self.trades_total.labels(
            strategy=settings.STRATEGY_CONFIG['name'],
            symbol=settings.SYMBOL
        ).inc()
        
        trade_details = {
            'timestamp': datetime.now(),
            'symbol': settings.SYMBOL,
            'side': result['side'],
            'amount': result['amount'],
            'price': result['price'],
            'strategy_params': settings.STRATEGY_CONFIG,
            'analysis_data': analysis['data'].iloc[-1].to_dict()
        }
        
        self.analyzer.record_trade(trade_details)

    def _log_strategy_error(self, data):
        """Log strategy errors with context"""
        logger.error("Strategy error occurred with data snapshot: %s", data.iloc[-1].to_dict())


    async def _calculate_position_size(self, side: str) -> float:
        """Risk-adjusted position sizing"""
        balance = await self.exchange.fetch_balance()
        quote_currency = settings.SYMBOL.split('/')[1]
        free_balance = balance.get(quote_currency, {}).get('free', 0)
        
        return min(
            free_balance * settings.RISK_PERCENTAGE,
            settings.MAX_POSITION_SIZE
        )

# Legacy compatibility layer
async def legacy_main(mode: str = "live_trade"):
    """Main function for backward compatibility"""
    bot = TradingBot()
    
    try:
        if mode == "live_trade":
            await bot.initialize()
        elif mode == "backtest":
            # Existing backtest implementation
            pass
        elif mode == "paper_trade":
            # Existing paper trade implementation
            pass
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested...")
    finally:
        bot.stop_event.set()
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(legacy_main(mode="live_trade"))
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")