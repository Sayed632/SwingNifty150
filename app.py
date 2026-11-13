"""
SwingNifty150 - Streamlit Swing Trading Screener
Nifty 100 + Nifty Midcap 150 | Beta + Candle Analysis | Entry / SL / Targets | Position Calculator
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import json
from datetime import datetime
from pathlib import Path
import pytz

from data.tickertape import get_nifty100_and_midcap150, get_index_constituents
from data.market_data import analyze_stock, fetch_ohlcv, compute_indicators
from analysis.position import calculate_position

# -------------------- Page Config --------------------
st.set_page_config(
    page_title="SwingNifty150 | Swing Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST).strftime("%d %b %Y  %I:%M %p IST")

# -------------------- Sidebar --------------------
st.sidebar.title("⚙️ Filters")
st.sidebar.caption(f"Last refresh: {now_ist}")

universe_choice = st.sidebar.multiselect(
    "Universe",
    options=["Nifty 100", "Nifty Midcap 150"],
    default=["Nifty 100", "Nifty Midcap 150"],
)

beta_min, beta_max = st.sidebar.slider(
    "Beta Range",
    min_value=0.0,
    max_value=2.5,
    value=(0.7, 1.6),
    step=0.1,
)

rsi_min, rsi_max = st.sidebar.slider(
    "RSI Range",
    min_value=10,
    max_value=80,
    value=(25, 60),
    step=1,
)

min_score = st.sidebar.slider("Minimum Bullish Score", 0, 8, 3)

show_only_signals = st.sidebar.checkbox("Show only BUY / STRONG BUY", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Position Calculator Defaults")
default_capital = st.sidebar.number_input("Trading Capital (₹)", value=200000, step=10000)
default_risk = st.sidebar.slider("Risk per trade (%)", 0.5, 3.0, 1.0, 0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Data Source")
use_cache = st.sidebar.checkbox("Use daily pre-computed cache (fast)", value=True)
force_live = st.sidebar.checkbox("Force live scan (slow, 40-70s)", value=False)
st.sidebar.caption("Cache is refreshed every weekday ~4:15 PM IST via GitHub Actions")
run_scan = st.sidebar.button("🚀 Load / Refresh", type="primary", use_container_width=True)

# -------------------- Header --------------------
st.title("📈 SwingNifty150")
st.markdown(
    "**Swing Trade Scanner** for **Nifty 100 + Nifty Midcap 150**  \n"
    "Beta • Candle Analysis • Entry / Stop-Loss / Targets • Position Sizing"
)

# -------------------- Caching helpers --------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_universe():
    return get_nifty100_and_midcap150()


@st.cache_data(ttl=900, show_spinner=False)
def analyze_batch(tickers: tuple, compute_beta: bool = False):
    results = []
    for t in tickers:
        try:
            res = analyze_stock(t, compute_beta=compute_beta)
            if res:
                results.append(res)
        except Exception:
            continue
        time.sleep(0.08)
    return results


# -------------------- Cache loader --------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_cached_scan():
    """Load pre-computed results from data/cache/latest_scan.json"""
    cache_path = Path(__file__).parent / "data" / "cache" / "latest_scan.json"
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            return json.load(f)
    except Exception:
        return None


# -------------------- Main Logic --------------------
if run_scan or "scan_results" not in st.session_state:

    cache_data = load_cached_scan() if use_cache and not force_live else None

    if cache_data and cache_data.get("results"):
        # Instant path — use daily cache
        all_results = cache_data["results"]
        st.session_state["scan_results"] = all_results
        st.session_state["cache_meta"] = {
            "generated_at_ist": cache_data.get("generated_at_ist"),
            "results_count": cache_data.get("results_count"),
            "universe_size": cache_data.get("universe_size"),
        }
        st.success(
            f"Loaded **{len(all_results)}** pre-computed signals "
            f"(generated {cache_data.get('generated_at_ist', 'N/A')})"
        )
    else:
        # Live scan path
        if force_live:
            st.info("Running live scan (this takes 40–70 seconds)...")
        else:
            st.warning("No cache found. Running live scan...")

        with st.spinner("Loading universe..."):
            universe_df = load_universe()

        if universe_df.empty:
            st.error("Could not fetch universe. Try again later.")
            st.stop()

        if universe_choice:
            universe_df = universe_df[universe_df["universe"].isin(universe_choice)]

        tickers = universe_df["ticker"].dropna().unique().tolist()
        st.info(f"Universe size: **{len(tickers)}** stocks")

        progress = st.progress(0, text="Scanning stocks...")
        status = st.empty()

        all_results = []
        chunk_size = 15
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            status.text(f"Analyzing {i+1} – {min(i+chunk_size, len(tickers))} of {len(tickers)}...")
            chunk_res = analyze_batch(tuple(chunk), compute_beta=False)
            all_results.extend(chunk_res)
            progress.progress(min((i + chunk_size) / len(tickers), 1.0))

        progress.empty()
        status.empty()

        st.session_state["scan_results"] = all_results
        st.session_state["universe_df"] = universe_df
        st.session_state["cache_meta"] = None

# -------------------- Display Results --------------------
if "scan_results" in st.session_state:
    results = st.session_state["scan_results"]
    universe_df = st.session_state.get("universe_df", pd.DataFrame())

    if not results:
        st.warning("No stocks returned from analysis.")
        st.stop()

    # Build dataframe
    rows = []
    for r in results:
        rows.append(
            {
                "Ticker": r["ticker"],
                "Price": r["price"],
                "Signal": r["signal"],
                "Confidence": r["confidence"],
                "Score": r["score"],
                "RSI": r["rsi"],
                "Beta": r["beta"] if r["beta"] is not None else "—",
                "Entry": r["entry"],
                "Stop Loss": r["stop_loss"],
                "Target 1": r["target1"],
                "Target 2": r["target2"],
                "R:R": r["risk_reward"],
                "Vol Ratio": r["volume_ratio"],
                "Reasons": " | ".join(r["reasons"][:4]),
            }
        )

    df = pd.DataFrame(rows)

    # Apply user filters
    df = df[
        (df["RSI"] >= rsi_min)
        & (df["RSI"] <= rsi_max)
        & (df["Score"] >= min_score)
    ]

    # Beta filter (handle missing)
    def beta_ok(b):
        try:
            return beta_min <= float(b) <= beta_max
        except Exception:
            return True  # keep if beta missing

    df = df[df["Beta"].apply(beta_ok)]

    if show_only_signals:
        df = df[df["Signal"].isin(["BUY", "STRONG BUY"])]

    df = df.sort_values(["Score", "R:R"], ascending=[False, False]).reset_index(drop=True)

    meta = st.session_state.get("cache_meta")
    if meta and meta.get("generated_at_ist"):
        st.caption(f"📦 Data from daily cache • Generated {meta['generated_at_ist']}")
    st.success(f"Found **{len(df)}** stocks matching your filters")

    # Color signal
    def color_signal(val):
        if val == "STRONG BUY":
            return "background-color: #0a7c42; color: white; font-weight: bold"
        if val == "BUY":
            return "background-color: #1f77b4; color: white"
        if val == "WATCH":
            return "background-color: #ffcc00; color: black"
        return ""

    st.dataframe(
        df.style.map(color_signal, subset=["Signal"]),
        use_container_width=True,
        height=480,
    )

    # -------------------- Detail View + Chart + Position Calc --------------------
    st.markdown("---")
    st.subheader("🔍 Stock Detail & Position Calculator")

    selected = st.selectbox(
        "Select a stock for detailed view",
        options=df["Ticker"].tolist() if not df.empty else [],
    )

    if selected:
        # Find original analysis result
        detail = next((r for r in results if r["ticker"] == selected), None)
        if detail:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Price", f"₹{detail['price']}")
            col2.metric("Signal", detail["signal"])
            col3.metric("RSI", detail["rsi"])
            col4.metric("Beta", detail["beta"] if detail["beta"] else "N/A")

            col5, col6, col7, col8 = st.columns(4)
            col5.metric("Entry", f"₹{detail['entry']}")
            col6.metric("Stop Loss", f"₹{detail['stop_loss']}")
            col7.metric("Target 1", f"₹{detail['target1']}")
            col8.metric("Target 2", f"₹{detail['target2']}")

            st.markdown(f"**Reasons:** {', '.join(detail['reasons'])}")

            # Position Calculator
            st.markdown("#### 📐 Position Size Calculator")
            c1, c2, c3 = st.columns(3)
            with c1:
                capital = st.number_input("Capital (₹)", value=float(default_capital), step=5000.0, key="pos_cap")
            with c2:
                risk_pct = st.number_input("Risk %", value=float(default_risk), min_value=0.1, max_value=5.0, step=0.1, key="pos_risk")
            with c3:
                lot = st.number_input("Lot Size", value=1, min_value=1, step=1, key="pos_lot")

            pos = calculate_position(capital, risk_pct, detail["entry"], detail["stop_loss"], lot)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Quantity", pos["quantity"])
            m2.metric("Capital Required", f"₹{pos['capital_required']:,.0f}")
            m3.metric("Max Loss (₹)", f"₹{pos['max_loss']:,.0f}")
            m4.metric("Risk Amount", f"₹{pos['risk_amount']:,.0f}")

            if pos["message"] != "OK":
                st.warning(pos["message"])

            # Candlestick Chart
            st.markdown("#### 📊 Daily Chart with Indicators")
            chart_df = detail.get("df")
            if chart_df is not None and not chart_df.empty:
                fig = make_subplots(
                    rows=3,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=("Price + EMA + Bollinger", "RSI", "MACD"),
                )

                # Candles
                fig.add_trace(
                    go.Candlestick(
                        x=chart_df.index,
                        open=chart_df["Open"],
                        high=chart_df["High"],
                        low=chart_df["Low"],
                        close=chart_df["Close"],
                        name="Price",
                    ),
                    row=1,
                    col=1,
                )

                # EMAs
                for col, color in [("EMA20", "orange"), ("EMA50", "blue"), ("EMA200", "purple")]:
                    if col in chart_df.columns:
                        fig.add_trace(
                            go.Scatter(x=chart_df.index, y=chart_df[col], name=col, line=dict(width=1.2, color=color)),
                            row=1,
                            col=1,
                        )

                # Bollinger
                if "BB_upper" in chart_df.columns:
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df["BB_upper"], name="BB Upper", line=dict(width=1, dash="dot", color="gray")),
                        row=1,
                        col=1,
                    )
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df["BB_lower"], name="BB Lower", line=dict(width=1, dash="dot", color="gray"), fill="tonexty", fillcolor="rgba(128,128,128,0.1)"),
                        row=1,
                        col=1,
                    )

                # Entry / SL / Targets horizontal lines
                fig.add_hline(y=detail["entry"], line_dash="dash", line_color="green", annotation_text="Entry", row=1, col=1)
                fig.add_hline(y=detail["stop_loss"], line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)
                fig.add_hline(y=detail["target1"], line_dash="dot", line_color="lime", annotation_text="T1", row=1, col=1)

                # RSI
                if "RSI" in chart_df.columns:
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df["RSI"], name="RSI", line=dict(color="purple")),
                        row=2,
                        col=1,
                    )
                    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
                    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

                # MACD
                if "MACD" in chart_df.columns:
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df["MACD"], name="MACD", line=dict(color="blue")),
                        row=3,
                        col=1,
                    )
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df["MACD_signal"], name="Signal", line=dict(color="orange")),
                        row=3,
                        col=1,
                    )
                    if "MACD_hist" in chart_df.columns:
                        colors = ["green" if v >= 0 else "red" for v in chart_df["MACD_hist"]]
                        fig.add_trace(
                            go.Bar(x=chart_df.index, y=chart_df["MACD_hist"], name="Hist", marker_color=colors),
                            row=3,
                            col=1,
                        )

                fig.update_layout(
                    height=750,
                    xaxis_rangeslider_visible=False,
                    showlegend=True,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Adjust filters in the sidebar and click **Run Scan** to start.")
    st.markdown(
        """
        ### What this app does
        - Pulls **Nifty 100** and **Nifty Midcap 150** constituents (Tickertape)
        - Calculates **Beta**, RSI, MACD, Bollinger, ATR, EMAs
        - Generates swing **Entry / Stop-Loss / Targets** (ATR-based)
        - Built-in **Position Size Calculator** based on your risk %
        - Interactive charts for any selected stock

        Click **Run Scan** when ready.
        """
    )

# Footer
st.markdown("---")
st.caption("SwingNifty150 • Educational tool only • Not investment advice • Data from public sources")
