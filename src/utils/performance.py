# src/utils/performance.py
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

class TradeMetrics:
    """Advanced trade performance analysis and risk management"""
    
    def __init__(self):
        self.trade_history = []
        self.equity_curve = []
        self.risk_free_rate = 0.02  # Default 2% annual risk-free rate
        
        # Risk parameters
        self.max_drawdown = 0
        self.current_drawdown = 0
        self.peak_equity = 0

    def record_trade(self, trade: Dict):
        """Record trade details with validation"""
        required_keys = ['timestamp', 'symbol', 'side', 'amount', 'price', 'fee']
        if not all(key in trade for key in required_keys):
            raise ValueError("Invalid trade structure")
            
        self.trade_history.append({
            'timestamp': datetime.now(),
            'symbol': trade['symbol'],
            'side': trade['side'],
            'quantity': trade['amount'],
            'price': trade['price'],
            'fee': trade['fee'],
            'pnl': self._calculate_pnl(trade)
        })
        self._update_equity_curve()

    def _calculate_pnl(self, trade: Dict) -> float:
        """Calculate preliminary PnL (needs market data for accurate calculation)"""
        # Implement your specific PnL calculation logic here
        return 0.0  # Placeholder

    def _update_equity_curve(self):
        """Update equity curve metrics"""
        current_equity = self.calculate_current_equity()
        self.equity_curve.append(current_equity)
        
        # Update drawdown metrics
        self.peak_equity = max(self.peak_equity, current_equity)
        self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

    def calculate_current_equity(self) -> float:
        """Calculate total equity from trade history"""
        return sum(trade['pnl'] for trade in self.trade_history)

    def get_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        returns = self._calculate_periodic_returns()
        
        return {
            'total_trades': len(self.trade_history),
            'win_rate': self._calculate_win_rate(),
            'sharpe_ratio': self._calculate_sharpe_ratio(returns),
            'max_drawdown': self.max_drawdown,
            'profit_factor': self._calculate_profit_factor(),
            'value_at_risk': self._calculate_var()
        }

    def _calculate_win_rate(self) -> float:
        """Calculate percentage of profitable trades"""
        if not self.trade_history:
            return 0.0
        profitable = sum(1 for t in self.trade_history if t['pnl'] > 0)
        return profitable / len(self.trade_history)

    def _calculate_periodic_returns(self) -> List[float]:
        """Calculate periodic returns for risk analysis"""
        # Implement your return calculation logic
        return [t['pnl'] for t in self.trade_history if t['pnl'] != 0]

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate annualized Sharpe ratio"""
        if not returns:
            return 0.0
            
        excess_returns = [r - self.risk_free_rate/252 for r in returns]
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        gains = sum(t['pnl'] for t in self.trade_history if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in self.trade_history if t['pnl'] < 0))
        return gains / losses if losses != 0 else float('inf')

    def _calculate_var(self, confidence_level: float = 0.95) -> float:
        """Calculate Value at Risk (VaR) using historical method"""
        returns = self._calculate_periodic_returns()
        if not returns:
            return 0.0
        return np.percentile(returns, (1 - confidence_level) * 100)

class RiskCalculator:
    """Advanced risk management calculations"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.portfolio_volatility = 0.0

    async def calculate_position_size(self, symbol: str, risk_percent: float) -> float:
        """Calculate position size based on volatility and account balance"""
        balance = await self.exchange.fetch_balance()
        if not balance:
            return 0.0
            
        equity = balance['total'].get('USDT', 0)
        volatility = await self._get_volatility(symbol)
        
        risk_capital = equity * risk_percent
        return risk_capital / volatility if volatility != 0 else 0.0

    async def _get_volatility(self, symbol: str, window: int = 14) -> float:
        """Calculate historical volatility for a symbol"""
        data = await self.exchange.fetch_ohlcv(symbol, '1d', limit=window)
        if len(data) < window:
            return 0.0
            
        closes = [entry[4] for entry in data]
        returns = np.diff(closes) / closes[:-1]
        return np.std(returns) * np.sqrt(252)

class TradeAnalyzer(TradeMetrics, RiskCalculator):
    """Combined trade analysis and risk management"""
    
    def __init__(self, exchange=None):
        TradeMetrics.__init__(self)
        RiskCalculator.__init__(self, exchange)
        
    async def acceptable_volatility(self, data: pd.DataFrame) -> bool:
        """Determine if market volatility is within acceptable range"""
        current_volatility = await self._get_volatility(data['symbol'].iloc[0])
        return current_volatility <= self.portfolio_volatility * 1.5