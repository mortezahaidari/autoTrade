# File: backtesting/backtester.py
import logging
import numpy as np

logger = logging.getLogger(__name__)

class Backtester:
    def __init__(self, initial_balance=10000, commission=0.001, slippage=0.0005, latency=1, trade_size=0.1):
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        self.latency = latency
        self.trade_size = trade_size
        self.balance = initial_balance
        self.position = 0  # 0 = no position, >0 = long position
        self.trades = []
        self.equity_curve = []

    def execute_trade(self, signal, price, timestamp):
        """
        Executes a trade based on the given signal.
        
        Args:
            signal (str): Trading signal (e.g., 'buy', 'sell', 'strong_buy', 'strong_sell').
            price (float): Current price of the asset.
            timestamp: Timestamp of the trade.
        """
        logger.info(f"Processing signal: {signal}, Position: {self.position}, Price: {price}")

        # Adjust price for slippage
        if signal in ['buy', 'strong_buy']:
            price *= (1 + self.slippage)
        elif signal in ['sell', 'strong_sell']:
            price *= (1 - self.slippage)

        if signal in ['buy', 'strong_buy'] and self.position == 0:
            # Execute buy order
            position_size = (self.balance * self.trade_size) / price
            self.position = position_size
            self.balance -= position_size * price * (1 + self.commission)
            self.trades.append({'type': 'buy', 'price': price, 'timestamp': timestamp, 'size': position_size})
            logger.info(f"📈 {signal.upper()} order executed at ${price:.2f}, Size: {position_size:.4f}")

        elif signal in ['sell', 'strong_sell'] and self.position > 0:
            # Execute sell order
            self.balance += self.position * price * (1 - self.commission)
            self.position = 0  # Reset position after selling
            self.trades.append({'type': 'sell', 'price': price, 'timestamp': timestamp, 'size': self.position})
            logger.info(f"📉 {signal.upper()} order executed at ${price:.2f}")

        else:
            logger.info(f"⚖️ No action taken (signal: {signal}, position: {self.position})")

        # Update equity curve
        self.equity_curve.append(self.balance + (self.position * price))

    def calculate_win_rate(self):
        """
        Calculates the win rate of the executed trades.
        
        Returns:
            float: Win rate as a percentage.
        """
        if not self.trades:
            return 0.0  # No trades executed

        wins = 0
        for i in range(1, len(self.trades), 2):  # Iterate over sell trades
            sell_trade = self.trades[i]
            buy_trade = self.trades[i - 1]
            if sell_trade['price'] > buy_trade['price']:  # Sell price > buy price = win
                wins += 1

        return (wins / (len(self.trades) // 2)) * 100  # Win rate as a percentage

    def calculate_risk_reward_ratio(self):
        """
        Calculates the risk-reward ratio of the executed trades.
        
        Returns:
            float: Risk-reward ratio.
        """
        if not self.trades:
            return float('inf')  # No trades executed

        total_profit = 0
        total_loss = 0

        for i in range(1, len(self.trades), 2):  # Iterate over sell trades
            sell_trade = self.trades[i]
            buy_trade = self.trades[i - 1]
            profit = sell_trade['price'] - buy_trade['price']
            if profit > 0:
                total_profit += profit
            else:
                total_loss += abs(profit)

        if total_loss == 0:
            return float('inf')  # No losses
        return total_profit / total_loss  # Risk-reward ratio

    def calculate_sharpe_ratio(self, risk_free_rate=0.0):
        """
        Calculates the Sharpe ratio of the equity curve.
        
        Args:
            risk_free_rate (float): Risk-free rate of return.
        
        Returns:
            float: Sharpe ratio.
        """
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        excess_returns = returns - risk_free_rate
        return np.mean(excess_returns) / np.std(excess_returns)

    def calculate_max_drawdown(self):
        """
        Calculates the maximum drawdown of the equity curve.
        
        Returns:
            float: Maximum drawdown as a percentage.
        """
        peak = self.equity_curve[0]
        max_drawdown = 0
        for value in self.equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown

    def calculate_profit_factor(self):
        """
        Calculates the profit factor of the trades.
        
        Returns:
            float: Profit factor.
        """
        gross_profit = sum(
            trade['size'] * (trade['price'] - self.trades[i-1]['price'])
            for i, trade in enumerate(self.trades)
            if trade['type'] == 'sell'
        )
        gross_loss = abs(sum(
            trade['size'] * (trade['price'] - self.trades[i-1]['price'])
            for i, trade in enumerate(self.trades)
            if trade['type'] == 'buy'
        ))
        return gross_profit / gross_loss if gross_loss != 0 else float('inf')

    def backtest(self, data, signals):
        """
        Backtests a trading strategy using historical data and signals.
        
        Args:
            data (pd.DataFrame): Historical OHLCV data.
            signals (pd.Series): Trading signals (e.g., 'buy', 'sell').
        
        Returns:
            dict: Backtest results including final balance, ROI, and other metrics.
        """
        for i in range(len(data)):
            signal = signals.iloc[i]
            price = data['close'].iloc[i]
            timestamp = data.index[i]

            # Execute trade based on signal
            self.execute_trade(signal, price, timestamp)

        # Calculate final balance
        if self.position > 0:
            self.balance += self.position * data['close'].iloc[-1] * (1 - self.commission)

        # Calculate metrics
        roi = (self.balance - self.initial_balance) / self.initial_balance * 100
        win_rate = self.calculate_win_rate()
        risk_reward_ratio = self.calculate_risk_reward_ratio()
        max_drawdown = self.calculate_max_drawdown()
        sharpe_ratio = self.calculate_sharpe_ratio()
        profit_factor = self.calculate_profit_factor()

        results = {
            'final_balance': self.balance,
            'roi': roi,
            'win_rate': win_rate,
            'risk_reward_ratio': risk_reward_ratio,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        return results