def update_trailing_stop(current_price, side, trailing_stop_percent=0.03):
    if side == "buy":
        return current_price * (1 - trailing_stop_percent)
    elif side == "sell":
        return current_price * (1 + trailing_stop_percent)