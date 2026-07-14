import io

import numpy as np
import pandas as pd
import pytest

from engine.backtest import _atr_result, _wilder_atr, run_backtest
from engine.data_loader import load_ohlc
from engine.params import StrategyParams


def _make_df(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    """rows: list of (High, Low, Close). Open is unused by the strategy, set to Close."""
    times = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    highs, lows, closes = zip(*rows)
    return pd.DataFrame({
        "Time": times,
        "Open": closes,
        "High": highs,
        "Low": lows,
        "Close": closes,
    })


def test_wilder_atr_matches_manual_calculation():
    high = np.array([10, 11, 12, 11, 13], dtype=float)
    low = np.array([8, 9, 10, 9, 11], dtype=float)
    close = np.array([9, 10, 11, 10, 12], dtype=float)

    atr = _wilder_atr(high, low, close, length=2)

    assert np.isnan(atr[0])
    assert atr[1] == pytest.approx(2.0)
    assert atr[2] == pytest.approx(2.0)
    assert atr[3] == pytest.approx(2.0)
    assert atr[4] == pytest.approx(2.5)


def test_entry_exit_intrabar_breakout_and_same_candle_new_signal():
    # entry_lookback=3, exit_lookback=2, atr_length=1 (ATR == True Range).
    rows = [
        (10, 9, 9.5),   # 0 floor
        (10, 9, 9.5),   # 1 floor
        (10, 9, 9.5),   # 2 floor
        (10, 9, 9.5),   # 3 floor (no breakout yet, High==HH not >)
        (12, 9.5, 11),  # 4 breakout: High(12) > HH(10) -> Long entry at 10
        (11, 10, 10.5), # 5 hold: Low(10) not < LL_exit(9)
        (11, 8, 9),     # 6 exit: Low(8) < LL_exit(9.5) -> exit at 9.5;
                        #    same candle also opens a fresh Short (LL_entry breaks)
                        #    which never closes before data ends and is excluded.
    ]
    df = _make_df(rows)
    params = StrategyParams(entry_lookback=3, exit_lookback=2, atr_length=1, use_filter=False)

    result = run_backtest(df, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.direction == "Long"
    assert trade.entry_price == pytest.approx(10)
    assert trade.exit_price == pytest.approx(9.5)
    assert trade.entry_atr == pytest.approx(2.5)
    assert trade.atr_result == pytest.approx((9.5 - 10) / 2.5)
    assert trade.bars_held == 2
    assert trade.exit_reason == "Exit Breakout"
    assert result.equity_curve == [pytest.approx(trade.atr_result)]


def test_atr_result_buffer_matches_spec_example():
    # Entry=100, Exit=110, ATR=2, Buffer=1 -> (110 - 101) / 2 = +4.5 ATR
    assert _atr_result("Long", 100, 110, 2, buffer=0) == pytest.approx(5.0)
    assert _atr_result("Long", 100, 110, 2, buffer=1) == pytest.approx(4.5)

    # Short mirrors the same conservative adjustment: adjusted entry = entry - buffer.
    assert _atr_result("Short", 100, 90, 2, buffer=0) == pytest.approx(5.0)
    assert _atr_result("Short", 100, 90, 2, buffer=1) == pytest.approx(4.5)


def test_atr_result_buffer_matches_real_world_examples():
    # Long: entry 25000, ATR 20, exit 25200, buffer 10
    # (25200 - 25000 - 10) / 20 = 190 / 20 = +9.5 ATR
    assert _atr_result("Long", 25000, 25200, 20, buffer=10) == pytest.approx(9.5)

    # Short: entry 25000, ATR 30, exit 24910, buffer 5
    # (25000 - 24910 - 5) / 30 = 85 / 30 = +2.8333 ATR
    assert _atr_result("Short", 25000, 24910, 30, buffer=5) == pytest.approx(85 / 30)


def test_execution_buffer_only_adjusts_atr_result_not_entries_or_exits():
    rows = [
        (10, 9, 9.5),
        (10, 9, 9.5),
        (10, 9, 9.5),
        (10, 9, 9.5),
        (12, 9.5, 11),  # breakout: Long entry at 10, entry_atr = 2.5
        (11, 10, 10.5),
        (11, 8, 9),     # exit at 9.5
    ]
    df = _make_df(rows)

    no_buffer = run_backtest(df, StrategyParams(entry_lookback=3, exit_lookback=2, atr_length=1, buffer=0.0))
    with_buffer = run_backtest(df, StrategyParams(entry_lookback=3, exit_lookback=2, atr_length=1, buffer=1.0))

    trade_a, trade_b = no_buffer.trades[0], with_buffer.trades[0]
    assert trade_a.entry_price == trade_b.entry_price == pytest.approx(10)
    assert trade_a.exit_price == trade_b.exit_price == pytest.approx(9.5)
    assert trade_a.bars_held == trade_b.bars_held

    # Buffer adjusts entry to 10 + 1 = 11 for this Long trade.
    assert trade_b.atr_result == pytest.approx((9.5 - 11) / 2.5)
    assert trade_b.atr_result < trade_a.atr_result


def _leg(breakout_low: float) -> list[tuple[float, float, float]]:
    return [
        (10, 0, 5),               # floor
        (10, 0, 5),               # floor
        (10, 0, 5),               # floor
        (20, breakout_low, 12),   # breakout
        (10, 1, 5),               # pullback / exit trigger
    ]


def _filter_test_rows():
    rows = []
    rows += _leg(15)  # leg 1: real trade, wins (exit 15 > entry 10)
    rows += _leg(5)   # leg 2: would lose (exit 5 < entry 10) if taken
    rows += _leg(18)  # leg 3: real trade, wins (exit 18 > entry 10)
    return rows


def test_turtle_filter_skips_after_win_and_resumes_after_hypothetical_loss():
    df = _make_df(_filter_test_rows())
    params = StrategyParams(entry_lookback=3, exit_lookback=1, atr_length=1, use_filter=True)

    result = run_backtest(df, params)

    # Leg 2's breakout must be skipped entirely (filter chaining), leaving
    # exactly leg 1 and leg 3 as realized trades.
    assert len(result.trades) == 2
    assert result.trades[0].entry_price == pytest.approx(10)
    assert result.trades[0].exit_price == pytest.approx(15)
    assert result.trades[0].atr_result > 0

    assert result.trades[1].entry_price == pytest.approx(10)
    assert result.trades[1].exit_price == pytest.approx(18)
    assert result.trades[1].atr_result > 0


def test_turtle_filter_off_takes_every_breakout():
    df = _make_df(_filter_test_rows())
    params = StrategyParams(entry_lookback=3, exit_lookback=1, atr_length=1, use_filter=False)

    result = run_backtest(df, params)

    assert len(result.trades) == 3
    assert result.trades[1].exit_price == pytest.approx(5)
    assert result.trades[1].atr_result < 0  # leg 2 genuinely would have lost


def test_ema_filter_blocks_and_allows_long_entries():
    base_rows = [
        (10, 0, 5),
        (10, 0, 5),
        (10, 0, 5),
        (20, 15, None),  # Close filled in per case
        (10, 1, 5),
    ]
    params = StrategyParams(
        entry_lookback=3, exit_lookback=1, atr_length=1,
        use_filter=False, use_ema_filter=True, ema_length=3,
    )

    # Case A: breakout Close (12) above EMA (~8.5) -> Long allowed.
    rows_allowed = list(base_rows)
    rows_allowed[3] = (20, 15, 12)
    df_allowed = _make_df(rows_allowed)
    result_allowed = run_backtest(df_allowed, params)
    assert len(result_allowed.trades) == 1

    # Case B: breakout Close (2) below EMA (~3.5) -> Long blocked.
    rows_blocked = list(base_rows)
    rows_blocked[3] = (20, 15, 2)
    df_blocked = _make_df(rows_blocked)
    result_blocked = run_backtest(df_blocked, params)
    assert len(result_blocked.trades) == 0


def test_load_ohlc_detects_columns_case_insensitively_and_sorts():
    csv = (
        "date,OPEN,high,Low,close\n"
        "2024-01-02,2,3,1,2.5\n"
        "2024-01-01,1,2,0.5,1.5\n"
    )
    df = load_ohlc(io.StringIO(csv))

    assert list(df.columns) == ["Time", "Open", "High", "Low", "Close"]
    assert df["Time"].tolist() == sorted(df["Time"].tolist())
    assert df.iloc[0]["Close"] == pytest.approx(1.5)


def test_load_ohlc_raises_on_missing_column():
    csv = "date,open,high,close\n2024-01-01,1,2,1.5\n"
    with pytest.raises(ValueError):
        load_ohlc(io.StringIO(csv))


def test_load_ohlc_ignores_mt_broker_export_columns():
    # MetaTrader-style export: Date, Open, High, Low, Close, Tick Volume, Volume, Spread.
    csv = (
        "Date,Open,High,Low,Close,Tick Volume,Volume,Spread\n"
        "2024-01-01,1,2,0.5,1.5,120,45000,10\n"
        "2024-01-02,2,3,1,2.5,98,38000,12\n"
    )
    df = load_ohlc(io.StringIO(csv))

    assert list(df.columns) == ["Time", "Open", "High", "Low", "Close"]
    assert len(df) == 2


def test_load_ohlc_handles_tab_separated_mt5_export_with_split_date_time():
    # Classic MT5 export: tab-separated, angle-bracket headers, separate DATE/TIME columns.
    tsv = (
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2024.01.02\t00:00:00\t2\t3\t1\t2.5\t500\t1200\t10\n"
        "2024.01.01\t00:00:00\t1\t2\t0.5\t1.5\t400\t1000\t12\n"
    )
    df = load_ohlc(io.StringIO(tsv))

    assert list(df.columns) == ["Time", "Open", "High", "Low", "Close"]
    assert df["Time"].tolist() == sorted(df["Time"].tolist())
    assert df.iloc[0]["Close"] == pytest.approx(1.5)
