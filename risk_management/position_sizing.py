def calculate_position_size(account_balance, risk_per_trade=0.01):
    return account_balance * risk_per_trade

def calculate_stop_loss(data, atr_multiplier=2):
    atr = data['ATR'].iloc[-1]
    return data['Close'].iloc[-1] - atr_multiplier * atr