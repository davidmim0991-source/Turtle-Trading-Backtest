import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from engine.backtest import run_backtest
from engine.data_loader import load_ohlc
from engine.params import StrategyParams

st.set_page_config(
    page_title="Turtle Backtester",
    page_icon=":material/candlestick_chart:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Visual polish only — does not affect backtest calculations.
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Sora:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

      .stApp {
        background:
          radial-gradient(1200px 600px at 8% -10%, rgba(45, 212, 191, 0.08), transparent 55%),
          radial-gradient(900px 500px at 100% 0%, rgba(56, 189, 248, 0.06), transparent 50%);
      }

      .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1180px;
      }

      .tb-hero {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem 2rem;
        margin-bottom: 1.75rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.22);
      }

      .tb-brand {
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: clamp(1.75rem, 3vw, 2.15rem);
        letter-spacing: -0.03em;
        line-height: 1.15;
        margin: 0;
      }

      .tb-brand span {
        color: #2DD4BF;
      }

      .tb-tagline {
        margin: 0.35rem 0 0;
        font-size: 0.98rem;
        color: #94A3B8;
        max-width: 34rem;
        line-height: 1.45;
      }

      .tb-chip {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #5EEAD4;
        border: 1px solid rgba(45, 212, 191, 0.35);
        background: rgba(45, 212, 191, 0.08);
        border-radius: 999px;
        padding: 0.4rem 0.85rem;
        white-space: nowrap;
      }

      .tb-section {
        font-family: 'Sora', sans-serif;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #94A3B8;
        margin: 0 0 0.85rem;
      }

      .tb-empty {
        text-align: center;
        padding: 2.5rem 1.5rem;
        border: 1px dashed rgba(148, 163, 184, 0.35);
        border-radius: 12px;
        background: rgba(20, 28, 39, 0.35);
      }

      .tb-empty h3 {
        font-family: 'Sora', sans-serif;
        font-size: 1.15rem;
        margin: 0 0 0.4rem;
      }

      .tb-empty p {
        margin: 0;
        color: #94A3B8;
        font-size: 0.95rem;
      }

      div[data-testid="stForm"] {
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 12px;
        padding: 1.1rem 1.15rem 0.85rem;
        background: rgba(20, 28, 39, 0.45);
      }

      div[data-testid="stMetric"] {
        background: rgba(20, 28, 39, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 10px;
        padding: 0.85rem 1rem;
      }

      div[data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
      }

      div[data-testid="stMetricLabel"] p {
        font-size: 0.82rem !important;
        letter-spacing: 0.02em;
      }

      [data-testid="stFileUploaderDropzone"] {
        border-radius: 10px !important;
      }

      .stTabs [data-baseweb="tab-list"] {
        gap: 0.35rem;
      }

      .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.55rem 1rem;
      }

      @media (prefers-color-scheme: light) {
        .stApp {
          background:
            radial-gradient(1100px 520px at 0% -5%, rgba(15, 118, 110, 0.07), transparent 55%),
            radial-gradient(800px 420px at 100% 0%, rgba(2, 132, 199, 0.05), transparent 50%),
            #F3F5F8;
        }
        .tb-brand span { color: #0F766E; }
        .tb-tagline { color: #64748B; }
        .tb-chip {
          color: #0F766E;
          border-color: rgba(15, 118, 110, 0.3);
          background: rgba(15, 118, 110, 0.08);
        }
        .tb-section { color: #64748B; }
        .tb-empty {
          background: rgba(255, 255, 255, 0.7);
          border-color: rgba(100, 116, 139, 0.35);
        }
        div[data-testid="stForm"] {
          background: rgba(255, 255, 255, 0.85);
          border-color: rgba(208, 215, 226, 0.95);
        }
        div[data-testid="stMetric"] {
          background: #FFFFFF;
          border-color: #D0D7E2;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="tb-hero">
      <div>
        <p class="tb-brand">Turtle <span>Backtester</span></p>
        <p class="tb-tagline">
          Deterministic ATR backtesting for the classic Turtle Trading System —
          upload OHLC data, set rules, inspect equity and trade quality.
        </p>
      </div>
      <div class="tb-chip">ATR · Breakouts · Risk units</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="tb-section">Setup</p>', unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("##### :material/upload_file: Historical data")
    uploaded_file = st.file_uploader(
        "Upload OHLC CSV (Date, Open, High, Low, Close)",
        type="csv",
        help="Requires Date/Time, Open, High, Low, Close columns. Any other "
             "columns (e.g. Tick Volume, Volume, Spread) are ignored.",
        label_visibility="collapsed",
    )

    with st.form("params_form"):
        st.markdown("##### :material/tune: Strategy parameters")
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_lookback = st.number_input("Entry lookback", min_value=1, value=20, step=1)
        with col2:
            exit_lookback = st.number_input("Exit lookback", min_value=1, value=10, step=1)
        with col3:
            atr_length = st.number_input("ATR length", min_value=2, value=14, step=1)

        col4, col5, col6, col7 = st.columns(4)
        with col4:
            use_filter = st.checkbox("Enable original Turtle filter", value=False)
        with col5:
            use_ema_filter = st.checkbox("Enable EMA trend filter", value=False)
        with col6:
            ema_length = st.number_input(
                "EMA length", min_value=2, value=200, step=1, disabled=not use_ema_filter
            )
        with col7:
            buffer = st.number_input(
                "Execution buffer (points)", min_value=0.0, value=0.0, step=0.1,
                help="Simulates execution delay, spread, and slippage. Only "
                     "adjusts the ATR performance calculation — never entries, "
                     "exits, or signals.",
            )

        run_clicked = st.form_submit_button(
            "Run backtest", icon=":material/play_arrow:", type="primary", use_container_width=True
        )

if run_clicked:
    if uploaded_file is None:
        st.error("Please upload a CSV file first.", icon=":material/error:")
    else:
        df = load_ohlc(uploaded_file)
        params = StrategyParams(
            entry_lookback=int(entry_lookback),
            exit_lookback=int(exit_lookback),
            atr_length=int(atr_length),
            use_filter=use_filter,
            use_ema_filter=use_ema_filter,
            ema_length=int(ema_length),
            buffer=float(buffer),
        )
        st.session_state["result"] = run_backtest(df, params)

result = st.session_state.get("result")

if result is None:
    st.markdown(
        """
        <div class="tb-empty">
          <h3>No backtest yet</h3>
          <p>Upload an OHLC CSV, set parameters, and run the backtest to see equity, stats, and trades.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    stats = result.statistics

    trade_df = pd.DataFrame([{
        "Trade Number": t.trade_number,
        "Direction": t.direction,
        "Entry Date": t.entry_time,
        "Exit Date": t.exit_time,
        "Entry Price": t.entry_price,
        "Exit Price": t.exit_price,
        "Entry ATR": t.entry_atr,
        "Result (ATR)": t.atr_result,
        "Bars Held": t.bars_held,
        "Exit Reason": t.exit_reason,
    } for t in result.trades])
    monthly_df = pd.DataFrame(result.monthly_performance).rename(
        columns={"month": "Month", "net_atr": "Net ATR"}
    )
    equity_df = pd.DataFrame({
        "Trade": range(1, len(result.equity_curve) + 1),
        "Equity (ATR)": result.equity_curve,
    })

    st.markdown('<p class="tb-section">Results</p>', unsafe_allow_html=True)

    header_col, export_col = st.columns([4, 1], vertical_alignment="bottom")
    with header_col:
        st.markdown("### :material/query_stats: Performance summary")
    with export_col:
        stats_df = pd.DataFrame(stats.items(), columns=["Metric", "Value"])
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            stats_df.to_excel(writer, sheet_name="Statistics", index=False)
            trade_df.to_excel(writer, sheet_name="Trade log", index=False)
            monthly_df.to_excel(writer, sheet_name="Monthly performance", index=False)
            equity_df.to_excel(writer, sheet_name="Equity curve", index=False)
        st.download_button(
            "Export",
            data=excel_buffer.getvalue(),
            file_name="turtle_backtest_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            use_container_width=True,
        )

    if stats["number_of_trades"] == 0:
        st.info("No trades were generated for these parameters.", icon=":material/info:")
    else:
        if stats["net_atr"] > 0:
            st.badge("Profitable", icon=":material/trending_up:", color="green")
        elif stats["net_atr"] < 0:
            st.badge("Unprofitable", icon=":material/trending_down:", color="red")
        else:
            st.badge("Break-even", icon=":material/trending_flat:", color="gray")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Net ATR", f"{stats['net_atr']:.2f}", border=True,
            chart_data=result.equity_curve, chart_type="line",
        )
        c2.metric("Max drawdown", f"{stats['max_drawdown']:.2f}", border=True)
        c3.metric("Win rate", f"{stats['win_rate']:.1f}%", border=True)
        c4.metric("Weekly win rate", f"{stats['weekly_win_rate']:.1f}%", border=True)

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Avg winning week", f"{stats['avg_winning_week']:.2f}", border=True)
        c6.metric("Avg losing week", f"{stats['avg_losing_week']:.2f}", border=True)
        c7.metric("Avg week (all)", f"{stats['avg_week']:.2f}", border=True)
        c8.metric("Number of trades", stats["number_of_trades"], border=True)

    if result.equity_curve:
        st.markdown("### :material/show_chart: Equity curve")
        fig = px.area(equity_df, x="Trade", y="Equity (ATR)", markers=True)
        fig.add_hline(y=0, line_dash="dot", opacity=0.4)
        fig.update_traces(
            line=dict(width=2.5, color="#2DD4BF"),
            fillcolor="rgba(45, 212, 191, 0.18)",
            marker=dict(size=6, color="#5EEAD4", line=dict(width=0)),
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Source Sans 3, sans-serif", color="#94A3B8"),
            xaxis=dict(showgrid=False, zeroline=False, title_font=dict(size=12)),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(148, 163, 184, 0.15)",
                zeroline=False,
                title_font=dict(size=12),
            ),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

    tab_trades, tab_monthly = st.tabs(
        [":material/table_chart: Trade log", ":material/calendar_month: Monthly performance"]
    )

    with tab_trades:
        if result.trades:
            st.dataframe(
                trade_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Entry Price": st.column_config.NumberColumn(format="%.4f"),
                    "Exit Price": st.column_config.NumberColumn(format="%.4f"),
                    "Entry ATR": st.column_config.NumberColumn(format="%.4f"),
                    "Result (ATR)": st.column_config.NumberColumn(format="%+.2f"),
                },
            )
        else:
            st.info("No trades were generated for these parameters.", icon=":material/info:")

    with tab_monthly:
        if not monthly_df.empty:
            st.dataframe(
                monthly_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Net ATR": st.column_config.NumberColumn(format="%+.2f"),
                },
            )
            if len(monthly_df) > 1:
                bar = go.Figure(
                    go.Bar(
                        x=monthly_df["Month"].astype(str),
                        y=monthly_df["Net ATR"],
                        marker_color=[
                            "#34D399" if v >= 0 else "#FB7185"
                            for v in monthly_df["Net ATR"]
                        ],
                    )
                )
                bar.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Source Sans 3, sans-serif", color="#94A3B8"),
                    xaxis=dict(showgrid=False, title=None),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(148, 163, 184, 0.15)",
                        title="Net ATR",
                    ),
                    height=320,
                )
                st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("No trades were generated for these parameters.", icon=":material/info:")
