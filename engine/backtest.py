from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from engine.params import StrategyParams
from engine.statistics import compute_monthly_atr, compute_statistics


@dataclass
class Trade:
    trade_number: int
    direction: str  # "Long" or "Short"
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    entry_atr: float
    atr_result: float
    bars_held: int
    exit_reason: str


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    statistics: dict = field(default_factory=dict)
    monthly_performance: list = field(default_factory=list)


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int) -> np.ndarray:
    n = len(high)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev_close = close[:-1]
    tr[1:] = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - prev_close),
        np.abs(low[1:] - prev_close),
    ])

    atr = np.full(n, np.nan)
    if n < length:
        return atr

    atr[length - 1] = tr[:length].mean()
    for i in range(length, n):
        atr[i] = (atr[i - 1] * (length - 1) + tr[i]) / length
    return atr


def _rolling_max_shifted(series: pd.Series, length: int) -> np.ndarray:
    return series.rolling(window=length).max().shift(1).to_numpy()


def _rolling_min_shifted(series: pd.Series, length: int) -> np.ndarray:
    return series.rolling(window=length).min().shift(1).to_numpy()


def _ema(series: pd.Series, length: int) -> np.ndarray:
    return series.ewm(span=length, adjust=False).mean().to_numpy()


def _atr_result(direction: str, entry_price: float, exit_price: float, entry_atr: float, buffer: float) -> float:
    """ATR result using a buffer-adjusted entry price.

    The buffer simulates execution delay/spread/slippage. It never affects
    entries, exits, or signals — only this performance calculation.
    """
    if direction == "Long":
        adjusted_entry = entry_price + buffer
        return (exit_price - adjusted_entry) / entry_atr
    adjusted_entry = entry_price - buffer
    return (adjusted_entry - exit_price) / entry_atr


def _scan_hypothetical_exit(
    start_i: int,
    direction: str,
    entry_price: float,
    entry_atr: float,
    buffer: float,
    n: int,
    high: np.ndarray,
    low: np.ndarray,
    hh_exit: np.ndarray,
    ll_exit: np.ndarray,
) -> Optional[float]:
    """Walk forward to find the exit result a skipped breakout would have had.

    Returns the ATR result, or None if the hypothetical trade never exits
    before the end of the dataset (left unclassified in that edge case).
    """
    for j in range(start_i, n):
        if direction == "Long":
            if not np.isnan(ll_exit[j]) and low[j] < ll_exit[j]:
                return _atr_result(direction, entry_price, ll_exit[j], entry_atr, buffer)
        else:
            if not np.isnan(hh_exit[j]) and high[j] > hh_exit[j]:
                return _atr_result(direction, entry_price, hh_exit[j], entry_atr, buffer)
    return None


def run_backtest(df: pd.DataFrame, params: StrategyParams) -> BacktestResult:
    n = len(df)
    time_arr = df["Time"].to_numpy()
    open_ = df["Open"].to_numpy(dtype=float)
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)

    atr = _wilder_atr(high, low, close, params.atr_length)
    hh_entry = _rolling_max_shifted(df["High"], params.entry_lookback)
    ll_entry = _rolling_min_shifted(df["Low"], params.entry_lookback)
    hh_exit = _rolling_max_shifted(df["High"], params.exit_lookback)
    ll_exit = _rolling_min_shifted(df["Low"], params.exit_lookback)
    ema = _ema(df["Close"], params.ema_length) if params.use_ema_filter else None

    position = None  # dict: direction, entry_price, entry_atr, entry_time, entry_index
    trades: list[Trade] = []
    equity_curve: list[float] = []
    balance = 0.0
    trade_counter = 0
    last_result = {"Long": None, "Short": None}

    for i in range(n):
        # 1. Check exit first, if a position is open.
        if position is not None:
            direction = position["direction"]
            exit_price = None
            if direction == "Long" and not np.isnan(ll_exit[i]) and low[i] < ll_exit[i]:
                exit_price = ll_exit[i]
            elif direction == "Short" and not np.isnan(hh_exit[i]) and high[i] > hh_exit[i]:
                exit_price = hh_exit[i]

            if exit_price is not None:
                atr_result = _atr_result(
                    direction, position["entry_price"], exit_price, position["entry_atr"], params.buffer
                )

                trade_counter += 1
                balance += atr_result
                trades.append(Trade(
                    trade_number=trade_counter,
                    direction=direction,
                    entry_time=position["entry_time"],
                    exit_time=time_arr[i],
                    entry_price=position["entry_price"],
                    exit_price=exit_price,
                    entry_atr=position["entry_atr"],
                    atr_result=atr_result,
                    bars_held=i - position["entry_index"],
                    exit_reason="Exit Breakout",
                ))
                equity_curve.append(balance)
                last_result[direction] = "win" if atr_result > 0 else "loss"
                position = None

        # 2. Check entry, if flat (whether already flat, or just closed above).
        if position is None:
            long_signal = not np.isnan(hh_entry[i]) and high[i] > hh_entry[i]
            short_signal = not np.isnan(ll_entry[i]) and low[i] < ll_entry[i]

            direction = None
            entry_price = None
            if long_signal:
                direction = "Long"
                entry_price = hh_entry[i]
            elif short_signal:
                direction = "Short"
                entry_price = ll_entry[i]

            if direction is not None:
                entry_atr = atr[i]
                if params.use_ema_filter and ema is not None:
                    if direction == "Long" and not (close[i] > ema[i]):
                        direction = None
                    elif direction == "Short" and not (close[i] < ema[i]):
                        direction = None

            if direction is not None and (np.isnan(entry_atr) or entry_atr <= 0):
                direction = None

            if direction is not None:
                if params.use_filter and last_result[direction] == "win":
                    # Skip this breakout, but still simulate it hypothetically
                    # so the filter's chained state stays correct for the
                    # next breakout in this direction. Never touches equity.
                    hyp_result = _scan_hypothetical_exit(
                        i + 1, direction, entry_price, entry_atr, params.buffer, n, high, low, hh_exit, ll_exit
                    )
                    if hyp_result is not None:
                        last_result[direction] = "win" if hyp_result > 0 else "loss"
                else:
                    position = {
                        "direction": direction,
                        "entry_price": entry_price,
                        "entry_atr": entry_atr,
                        "entry_time": time_arr[i],
                        "entry_index": i,
                    }

    statistics = compute_statistics(trades, equity_curve)
    monthly_performance = compute_monthly_atr(trades)
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        statistics=statistics,
        monthly_performance=monthly_performance,
    )
