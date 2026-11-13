"""
Market data using yfinance + simple technical indicators.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from typing import Optional, Dict, List
import warnings

warnings.filterwarnings("ignore")


def fetch_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV for an NSE ticker. Accepts with or without .NS suffix."""
    symbol = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except Exception:
        return None


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, MACD, Bollinger, ATR, EMAs to OHLCV dataframe."""
    if df is None or len(df) < 30:
        return df

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # RSI
    rsi = RSIIndicator(close=close, window=14)
    df["RSI"] = rsi.rsi()

    # MACD
    macd = MACD(close=close)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()

    # Bollinger
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_mid"] = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()
    df["BB_pct"] = (close - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"])

    # ATR
    atr = AverageTrueRange(high=high, low=low, close=close, window=14)
    df["ATR"] = atr.average_true_range()

    # EMAs
    df["EMA20"] = EMAIndicator(close=close, window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(close=close, window=50).ema_indicator()
    df["EMA200"] = EMAIndicator(close=close, window=200).ema_indicator()

    # Volume SMA
    df["Vol_SMA20"] = df["Volume"].rolling(20).mean()

    return df


_beta_cache: Dict[str, Optional[float]] = {}


def get_beta(ticker: str, period: str = "1y", use_cache: bool = True) -> Optional[float]:
    """Simple beta vs Nifty 50 using yfinance. Session-cached."""
    key = ticker.replace(".NS", "").upper()
    if use_cache and key in _beta_cache:
        return _beta_cache[key]
    try:
        stock = yf.Ticker(f"{key}.NS")
        hist = stock.history(period=period)
        nifty = yf.Ticker("^NSEI").history(period=period)
        if hist.empty or nifty.empty:
            _beta_cache[key] = None
            return None
        common = hist.index.intersection(nifty.index)
        if len(common) < 40:
            _beta_cache[key] = None
            return None
        stock_ret = hist.loc[common, "Close"].pct_change().dropna()
        nifty_ret = nifty.loc[common, "Close"].pct_change().dropna()
        aligned = pd.concat([stock_ret, nifty_ret], axis=1).dropna()
        aligned.columns = ["stock", "nifty"]
        if len(aligned) < 40:
            _beta_cache[key] = None
            return None
        cov = np.cov(aligned["stock"], aligned["nifty"])[0, 1]
        var = np.var(aligned["nifty"])
        if var == 0:
            _beta_cache[key] = None
            return None
        beta = round(float(cov / var), 2)
        _beta_cache[key] = beta
        return beta
    except Exception:
        _beta_cache[key] = None
        return None


def analyze_stock(ticker: str, compute_beta: bool = False) -> Optional[Dict]:
    """
    Full analysis for one stock.
    Returns dict with price, indicators, signal, entry/sl/targets, beta etc.
    """
    df = fetch_ohlcv(ticker, period="1y")
    if df is None or len(df) < 50:
        return None

    df = compute_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest["Close"])
    atr = float(latest["ATR"]) if not pd.isna(latest["ATR"]) else close * 0.02
    rsi = float(latest["RSI"]) if not pd.isna(latest["RSI"]) else 50.0
    macd = float(latest["MACD"]) if not pd.isna(latest["MACD"]) else 0.0
    macd_sig = float(latest["MACD_signal"]) if not pd.isna(latest["MACD_signal"]) else 0.0
    ema20 = float(latest["EMA20"]) if not pd.isna(latest["EMA20"]) else close
    ema50 = float(latest["EMA50"]) if not pd.isna(latest["EMA50"]) else close
    ema200 = float(latest["EMA200"]) if not pd.isna(latest["EMA200"]) else close
    bb_pct = float(latest["BB_pct"]) if not pd.isna(latest["BB_pct"]) else 0.5
    vol = float(latest["Volume"])
    vol_sma = float(latest["Vol_SMA20"]) if not pd.isna(latest["Vol_SMA20"]) else vol

    # Simple swing bias logic
    bullish_score = 0
    reasons = []

    if close > ema20 > ema50:
        bullish_score += 2
        reasons.append("Price > EMA20 > EMA50")
    elif close > ema20:
        bullish_score += 1
        reasons.append("Price > EMA20")

    if close > ema200:
        bullish_score += 1
        reasons.append("Above EMA200")

    if 30 < rsi < 55:
        bullish_score += 1
        reasons.append(f"RSI healthy ({rsi:.1f})")
    elif rsi < 30:
        bullish_score += 2
        reasons.append(f"RSI oversold ({rsi:.1f})")

    if macd > macd_sig and macd > 0:
        bullish_score += 1
        reasons.append("MACD bullish")

    if bb_pct < 0.25:
        bullish_score += 1
        reasons.append("Near lower Bollinger")

    if vol > 1.3 * vol_sma:
        bullish_score += 1
        reasons.append("Volume spike")

    # Signal
    if bullish_score >= 5:
        signal = "STRONG BUY"
        confidence = "High"
    elif bullish_score >= 3:
        signal = "BUY"
        confidence = "Medium"
    elif bullish_score >= 1:
        signal = "WATCH"
        confidence = "Low"
    else:
        signal = "AVOID"
        confidence = "Low"

    # Levels (ATR based)
    entry = round(close, 2)
    stop_loss = round(close - 1.5 * atr, 2)
    target1 = round(close + 2.0 * atr, 2)
    target2 = round(close + 3.0 * atr, 2)
    risk_reward = round((target1 - entry) / (entry - stop_loss), 2) if entry > stop_loss else 0

    beta = get_beta(ticker) if compute_beta else None

    return {
        "ticker": ticker.replace(".NS", ""),
        "price": entry,
        "signal": signal,
        "confidence": confidence,
        "score": bullish_score,
        "reasons": reasons,
        "rsi": round(rsi, 1),
        "macd": round(macd, 3),
        "atr": round(atr, 2),
        "beta": beta,
        "entry": entry,
        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,
        "risk_reward": risk_reward,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "volume_ratio": round(vol / vol_sma, 2) if vol_sma else 1.0,
        "df": df.tail(120),  # keep recent data for charts
    }
