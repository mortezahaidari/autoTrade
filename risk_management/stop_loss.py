def set_stop_loss(entry_price, side, stop_loss_percent=0.10):
    if side == "buy":
        return entry_price * (1 - stop_loss_percent)
    elif side == "sell":
        return entry_price * (1 + stop_loss_percent)