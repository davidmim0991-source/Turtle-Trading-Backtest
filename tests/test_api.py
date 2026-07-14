"""API wiring tests — engine calculations stay covered by existing engine tests."""

import io

from fastapi.testclient import TestClient

from app import app
from engine.backtest import run_backtest
from engine.data_loader import load_ohlc
from engine.params import StrategyParams
from api.routes import serialize_result

client = TestClient(app)


def _sample_csv() -> bytes:
    import datetime as dt

    rows = ["Date,Open,High,Low,Close"]
    price = 100.0
    start = dt.date(2024, 1, 2)
    for i in range(120):
        day = start + dt.timedelta(days=i)
        high = price + 1.5
        low = price - 1.5
        close = price + (0.5 if i % 4 == 0 else -0.2)
        rows.append(f"{day.isoformat()},{price:.4f},{high:.4f},{low:.4f},{close:.4f}")
        price = close
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_index_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Turtle Backtester" in response.text
    assert "/static/js/app.js" in response.text


def test_backtest_matches_engine():
    csv_bytes = _sample_csv()
    params = {
        "entry_lookback": "20",
        "exit_lookback": "10",
        "atr_length": "14",
        "use_filter": "false",
        "use_ema_filter": "false",
        "ema_length": "200",
        "buffer": "0",
    }
    response = client.post(
        "/api/backtest",
        data=params,
        files={"file": ("sample.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    df = load_ohlc(io.BytesIO(csv_bytes))
    expected = serialize_result(
        run_backtest(
            df,
            StrategyParams(
                entry_lookback=20,
                exit_lookback=10,
                atr_length=14,
                use_filter=False,
                use_ema_filter=False,
                ema_length=200,
                buffer=0.0,
            ),
        )
    )
    assert payload["statistics"] == expected["statistics"]
    assert payload["equity_curve"] == expected["equity_curve"]
    assert payload["trades"] == expected["trades"]
    assert payload["monthly_performance"] == expected["monthly_performance"]


def test_export_xlsx():
    csv_bytes = _sample_csv()
    response = client.post(
        "/api/export",
        data={
            "entry_lookback": "20",
            "exit_lookback": "10",
            "atr_length": "14",
            "use_filter": "false",
            "use_ema_filter": "false",
            "ema_length": "200",
            "buffer": "0",
        },
        files={"file": ("sample.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert response.content[:2] == b"PK"
