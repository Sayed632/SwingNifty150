"""
Daily pre-computation script for SwingNifty150.
Runs via GitHub Actions after market close and saves results to data/cache/.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz

# Allow running from repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.tickertape import get_nifty100_and_midcap150
from data.market_data import analyze_stock

IST = pytz.timezone("Asia/Kolkata")
CACHE_DIR = ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def run_daily_scan(max_stocks: int = None) -> dict:
    print("=" * 60)
    print(f"SwingNifty150 Daily Scan — {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}")
    print("=" * 60)

    universe = get_nifty100_and_midcap150()
    if universe.empty:
        print("ERROR: Empty universe")
        return {}

    tickers = universe["ticker"].dropna().unique().tolist()
    if max_stocks:
        tickers = tickers[:max_stocks]

    print(f"Universe size: {len(tickers)}")

    results = []
    failed = []
    t0 = time.time()

    for i, t in enumerate(tickers, 1):
        try:
            res = analyze_stock(t, compute_beta=True)
            if res:
                # Drop the heavy dataframe before saving
                res_clean = {k: v for k, v in res.items() if k != "df"}
                results.append(res_clean)
            else:
                failed.append(t)
        except Exception as e:
            failed.append(t)
            print(f"  Failed {t}: {e}")

        if i % 25 == 0 or i == len(tickers):
            elapsed = time.time() - t0
            print(f"  [{i}/{len(tickers)}]  {len(results)} ok  |  {elapsed:.0f}s elapsed")

        time.sleep(0.07)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s — {len(results)} signals, {len(failed)} failed")

    # Build summary table
    rows = []
    for r in results:
        rows.append(
            {
                "ticker": r["ticker"],
                "price": r["price"],
                "signal": r["signal"],
                "confidence": r["confidence"],
                "score": r["score"],
                "rsi": r["rsi"],
                "beta": r.get("beta"),
                "entry": r["entry"],
                "stop_loss": r["stop_loss"],
                "target1": r["target1"],
                "target2": r["target2"],
                "risk_reward": r["risk_reward"],
                "volume_ratio": r["volume_ratio"],
                "reasons": " | ".join(r.get("reasons", [])[:5]),
                "ema20": r.get("ema20"),
                "ema50": r.get("ema50"),
                "ema200": r.get("ema200"),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["score", "risk_reward"], ascending=[False, False])

    # Save outputs
    today = datetime.now(IST).strftime("%Y-%m-%d")
    stamp = datetime.now(IST).strftime("%Y%m%d_%H%M")

    json_path = CACHE_DIR / "latest_scan.json"
    csv_path = CACHE_DIR / "latest_scan.csv"
    meta_path = CACHE_DIR / "latest_meta.json"
    hist_json = CACHE_DIR / f"scan_{stamp}.json"

    payload = {
        "generated_at": datetime.now(IST).isoformat(),
        "generated_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "universe_size": len(tickers),
        "results_count": len(results),
        "failed_count": len(failed),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }

    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"Saved {json_path}")

    # Keep a dated copy (optional history)
    with open(hist_json, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    if not df.empty:
        df.to_csv(csv_path, index=False)
        print(f"Saved {csv_path}")

    meta = {
        "last_run": datetime.now(IST).isoformat(),
        "last_run_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "results_count": len(results),
        "universe_size": len(tickers),
        "strong_buy": int((df["signal"] == "STRONG BUY").sum()) if not df.empty else 0,
        "buy": int((df["signal"] == "BUY").sum()) if not df.empty else 0,
        "watch": int((df["signal"] == "WATCH").sum()) if not df.empty else 0,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved {meta_path}")

    # Print top ideas
    if not df.empty:
        print("\n--- Top 10 by Score ---")
        print(df.head(10)[["ticker", "signal", "score", "rsi", "entry", "stop_loss", "target1", "risk_reward"]].to_string(index=False))

    return payload


if __name__ == "__main__":
    # Allow limiting for testing: python scripts/daily_scan.py 30
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_daily_scan(max_stocks=limit)
