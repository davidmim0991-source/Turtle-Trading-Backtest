import pandas as pd

_DATE_NAMES = {"date", "datetime", "timestamp"}
_TIME_ONLY_NAMES = {"time"}
_COLUMN_NAMES = {"open": "Open", "high": "High", "low": "Low", "close": "Close"}


def load_ohlc(file) -> pd.DataFrame:
    """Load a CSV into a clean, sorted OHLC DataFrame indexed by datetime.

    Accepts comma, tab, or semicolon-delimited files (auto-detected) and any
    casing for Date/Time/Datetime + Open/High/Low/Close columns. A separate
    Date + Time column pair (e.g. MetaTrader exports) is combined into one
    timestamp. Any other columns (Tick Volume, Volume, Spread, etc.) are
    ignored.
    """
    df = pd.read_csv(file, sep=None, engine="python")
    df.columns = [str(c).strip().strip("<>").strip() for c in df.columns]
    lower_to_actual = {c.lower(): c for c in df.columns}

    date_col = next((lower_to_actual[n] for n in _DATE_NAMES if n in lower_to_actual), None)
    time_col = next((lower_to_actual[n] for n in _TIME_ONLY_NAMES if n in lower_to_actual), None)
    if date_col is None:
        raise ValueError("CSV must contain a Date/Datetime/Timestamp column.")

    rename_map = {}
    for lower, canonical in _COLUMN_NAMES.items():
        if lower not in lower_to_actual:
            raise ValueError(f"CSV is missing required column: {canonical}")
        rename_map[lower_to_actual[lower]] = canonical

    df = df.rename(columns=rename_map)
    if time_col is not None and time_col != date_col:
        df["Time"] = pd.to_datetime(
            df[date_col].astype(str) + " " + df[time_col].astype(str), errors="coerce"
        )
    else:
        df["Time"] = pd.to_datetime(df[date_col], errors="coerce")

    df = df[["Time", "Open", "High", "Low", "Close"]]
    df = df.dropna(subset=["Time", "Open", "High", "Low", "Close"])
    df = df.drop_duplicates(subset="Time")
    df = df.sort_values("Time").reset_index(drop=True)

    return df
