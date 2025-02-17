def allocate_capital(weights, account_balance):
    allocations = {asset: weight * account_balance for asset, weight in weights.items()}
    return allocations