# File: tests/test_backtester.py
def test_backtester():
    data = pd.DataFrame({'close': [100, 101, 102, 101, 100]})
    signals = pd.Series(['buy', 'neutral', 'sell', 'neutral', 'buy'])
    backtester = Backtester()
    results = backtester.backtest(data, signals)
    assert results['final_balance'] > 0