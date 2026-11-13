"""
Tickertape data helpers (unofficial public JSON endpoints).
Used for index constituents and basic fundamental filters.
"""

import requests
import pandas as pd
from typing import List, Dict, Optional
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.tickertape.in/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Common Tickertape index sids
INDEX_SIDS = {
    "NIFTY100": ".NIFTY100",
    "NIFTY_MIDCAP_150": ".NIFTYMIDCAP150",
    "NIFTY50": ".NSEI",
    "NIFTY500": ".NIFTY500",
}


def _get(url: str, params: Optional[dict] = None, retries: int = 2) -> Optional[dict]:
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.8 * (attempt + 1))
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return None


def get_index_constituents(index_key: str = "NIFTY_MIDCAP_150") -> List[Dict]:
    """
    Returns list of dicts with ticker, name, sid etc. for the given index.
    index_key: one of INDEX_SIDS keys
    """
    sid = INDEX_SIDS.get(index_key, ".NIFTYMIDCAP150")
    url = f"https://api.tickertape.in/indices/constituents/{sid}"
    data = _get(url)
    if not data or "data" not in data:
        return []

    constituents = data.get("data", {}).get("constituents", [])
    result = []
    for c in constituents:
        info = c.get("info", {}) or c
        result.append(
            {
                "ticker": info.get("ticker") or info.get("symbol"),
                "name": info.get("name") or info.get("company"),
                "sid": info.get("sid"),
                "slug": info.get("slug"),
                "sector": (c.get("sector") or {}).get("name") if isinstance(c.get("sector"), dict) else c.get("sector"),
            }
        )
    return [r for r in result if r.get("ticker")]


def search_stock(query: str) -> Optional[Dict]:
    """Quick search for a stock on Tickertape."""
    url = "https://api.tickertape.in/search"
    data = _get(url, params={"text": query, "types": "stock"})
    if not data:
        return None
    stocks = data.get("data", {}).get("stocks", [])
    if stocks:
        s = stocks[0]
        return {
            "sid": s.get("sid"),
            "ticker": s.get("ticker"),
            "slug": s.get("slug"),
            "name": s.get("name"),
        }
    return None


def get_stock_overview(sid: str) -> Optional[Dict]:
    """Basic overview / ratios for a stock (includes beta if available)."""
    url = f"https://api.tickertape.in/stocks/overview/{sid}"
    data = _get(url)
    if not data or "data" not in data:
        return None
    return data["data"]


def get_nifty100_and_midcap150() -> pd.DataFrame:
    """Convenience: combined universe with source tag."""
    rows = []
    for key, label in [("NIFTY100", "Nifty 100"), ("NIFTY_MIDCAP_150", "Nifty Midcap 150")]:
        consts = get_index_constituents(key)
        for c in consts:
            c["universe"] = label
            rows.append(c)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Deduplicate preferring Nifty 100 if overlap
    df = df.drop_duplicates(subset=["ticker"], keep="first")
    return df.reset_index(drop=True)
