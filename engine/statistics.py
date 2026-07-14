import pandas as pd


def compute_statistics(trades: list, equity_curve: list) -> dict:
    n = len(trades)
    stats = {
        "number_of_trades": n,
        "net_atr": 0.0,
        "max_drawdown": 0.0,
        "win_rate": 0.0,
        "weekly_win_rate": 0.0,
        "avg_winning_week": 0.0,
        "avg_losing_week": 0.0,
        "avg_week": 0.0,
    }
    if n == 0:
        return stats

    stats["net_atr"] = equity_curve[-1]

    peak = 0.0
    max_dd = 0.0
    for balance in equity_curve:
        peak = max(peak, balance)
        max_dd = min(max_dd, balance - peak)
    stats["max_drawdown"] = max_dd

    wins = sum(1 for t in trades if t.atr_result > 0)
    stats["win_rate"] = wins / n * 100

    weekly: dict = {}
    prior_balance = 0.0
    for trade, balance in zip(trades, equity_curve):
        iso = pd.Timestamp(trade.exit_time).isocalendar()
        key = (iso.year, iso.week)
        if key not in weekly:
            weekly[key] = {"start": prior_balance, "end": balance}
        else:
            weekly[key]["end"] = balance
        prior_balance = balance

    winning_week_changes = []
    losing_week_changes = []
    for bounds in weekly.values():
        change = bounds["end"] - bounds["start"]
        if change > 0:
            winning_week_changes.append(change)
        else:
            losing_week_changes.append(change)

    total_weeks = len(winning_week_changes) + len(losing_week_changes)
    if total_weeks:
        stats["weekly_win_rate"] = len(winning_week_changes) / total_weeks * 100
    if winning_week_changes:
        stats["avg_winning_week"] = sum(winning_week_changes) / len(winning_week_changes)
    if losing_week_changes:
        stats["avg_losing_week"] = sum(losing_week_changes) / len(losing_week_changes)
    if total_weeks:
        stats["avg_week"] = sum(winning_week_changes + losing_week_changes) / total_weeks

    return stats


def compute_monthly_atr(trades: list) -> list[dict]:
    """Net ATR per calendar month, bucketed by each trade's exit time."""
    monthly: dict = {}
    for trade in trades:
        ts = pd.Timestamp(trade.exit_time)
        key = (ts.year, ts.month)
        monthly[key] = monthly.get(key, 0.0) + trade.atr_result

    return [
        {"month": f"{year:04d}-{month:02d}", "net_atr": net_atr}
        for (year, month), net_atr in sorted(monthly.items())
    ]
