import pandas as pd
import pytest

from engine.backtest import Trade
from engine.statistics import compute_monthly_atr, compute_statistics


def _trade(atr_result: float, exit_time: str) -> Trade:
    return Trade(
        trade_number=1,
        direction="Long",
        entry_time=pd.Timestamp(exit_time),
        exit_time=pd.Timestamp(exit_time),
        entry_price=0.0,
        exit_price=0.0,
        entry_atr=1.0,
        atr_result=atr_result,
        bars_held=1,
        exit_reason="Exit Breakout",
    )


def test_net_atr_and_max_drawdown_match_spec_example():
    # +5, +4, -8, -6, +7 -> balances 5, 9, 1, -5, 2
    results = [5, 4, -8, -6, 7]
    trades = [_trade(r, f"2024-01-{i + 1:02d}") for i, r in enumerate(results)]
    equity_curve = []
    balance = 0.0
    for r in results:
        balance += r
        equity_curve.append(balance)

    stats = compute_statistics(trades, equity_curve)

    assert stats["net_atr"] == pytest.approx(2.0)
    assert stats["max_drawdown"] == pytest.approx(-14.0)  # peak 9 -> trough -5
    assert stats["win_rate"] == pytest.approx(60.0)  # 3 of 5 trades positive
    assert stats["number_of_trades"] == 5


def test_weekly_win_rate_and_averages():
    # Week 1 (Mon 2024-01-01 / Wed 2024-01-03): +3, +2 -> winning week (+5)
    # Week 2 (Mon 2024-01-08 / Thu 2024-01-11): -1, -6 -> losing week (-7)
    trades = [
        _trade(3, "2024-01-01"),
        _trade(2, "2024-01-03"),
        _trade(-1, "2024-01-08"),
        _trade(-6, "2024-01-11"),
    ]
    equity_curve = [3, 5, 4, -2]

    stats = compute_statistics(trades, equity_curve)

    assert stats["weekly_win_rate"] == pytest.approx(50.0)
    assert stats["avg_winning_week"] == pytest.approx(5.0)
    assert stats["avg_losing_week"] == pytest.approx(-7.0)
    assert stats["avg_week"] == pytest.approx(-1.0)  # (+5 and -7) combined
    assert stats["max_drawdown"] == pytest.approx(-7.0)  # peak 5 -> trough -2


def test_no_trades_returns_zeroed_statistics():
    stats = compute_statistics([], [])

    assert stats["number_of_trades"] == 0
    assert stats["net_atr"] == 0.0
    assert stats["max_drawdown"] == 0.0
    assert stats["win_rate"] == 0.0
    assert stats["weekly_win_rate"] == 0.0
    assert stats["avg_week"] == 0.0


def test_compute_monthly_atr_buckets_by_exit_month():
    trades = [
        _trade(3, "2024-01-05"),
        _trade(2, "2024-01-20"),
        _trade(-4, "2024-02-10"),
    ]

    monthly = compute_monthly_atr(trades)

    assert monthly == [
        {"month": "2024-01", "net_atr": pytest.approx(5.0)},
        {"month": "2024-02", "net_atr": pytest.approx(-4.0)},
    ]


def test_compute_monthly_atr_empty_trades():
    assert compute_monthly_atr([]) == []
