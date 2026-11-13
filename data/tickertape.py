"""
Tickertape data helpers (unofficial public JSON endpoints).
Includes reliable fallbacks when endpoints return null / are blocked.
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

# Working SIDs (verified)
INDEX_SIDS = {
    "NIFTY100": ".NIFTY100",
    "NIFTY50": ".NSEI",
    "NIFTY500": ".NIFTY500",
}

# Curated liquid Midcap / Nifty Midcap 150 style names (fallback when API fails)
# These are common liquid midcaps frequently appearing in Nifty Midcap 150
MIDCAP_FALLBACK = [
    "PERSISTENT", "COFORGE", "LUPIN", "AUROPHARMA", "BIOCON", "ALKEM", "AJANTPHARM",
    "ABBOTINDIA", "GLAXO", "IPCALAB", "LAURUSLABS", "SYNGENE", "MAXHEALTH", "FORTIS",
    "APOLLOHOSP", "METROPOLIS", "LALPATHLAB", "INDHOTEL", "JUBLFOOD", "DEVYANI",
    "WESTLIFE", "SAPPHIRE", "ZOMATO", "NAUKRI", "POLICYBZR", "PAYTM", "NYKAA",
    "DELHIVERY", "MAZDOCK", "BDL", "HAL", "BEL", "BHEL", "BEML", "GRSE", "COCHINSHIP",
    "SOLARINDS", "DEEPAKNTR", "CLEAN", "PIIND", "SRF", "AARTIIND", "FLUOROCHEM",
    "ATUL", "FINEORG", "BALAMINES", "NOCIL", "ASHOKLEY", "TIINDIA", "MOTHERSON",
    "BHARATFORG", "ENDURANCE", "SONACOMS", "UNOMINDA", "SCHAEFFLER", "SKFINDIA",
    "CUMMINSIND", "THERMAX", "KIRLOSENG", "ELGIEQUIP", "AIAENG", "ESABINDIA",
    "APLAPOLLO", "JINDALSAW", "WELCORP", "RATNAMANI", "MAHSEAMLES", "KIRLOSBROS",
    "POLYCAB", "KEI", "FINCABLES", "HAVELLS", "CROMPTON", "VGUARD", "VOLTAS",
    "BLUESTARCO", "WHIRLPOOL", "ORIENTELEC", "DIXON", "AMBER", "KALYANKJIL",
    "TITAN", "PAGEIND", "RELAXO", "BATAINDIA", "METROBRAND", "TRENT", "ABFRL",
    "MANYAVAR", "RAYMOND", "ARVIND", "LODHA", "GODREJPROP", "PRESTIGE", "OBEROIRLTY",
    "BRIGADE", "SOBHA", "PHOENIXLTD", "DLF", "IBREALEST", "SUNTECK",
    "FEDERALBNK", "IDFCFIRSTB", "RBLBANK", "BANDHANBNK", "AUBANK", "CUB",
    "BANKINDIA", "MAHABANK", "IOB", "CENTRALBK", "UCOBANK", "PSB",
    "LICHSGFIN", "CANFINHOME", "AAVAS", "HOMEFIRST", "PNBHOUSING",
    "MUTHOOTFIN", "MANAPPURAM", "CHOLAFIN", "SUNDARMFIN", "M&MFIN", "BAJFINANCE",
    "BAJAJFINSV", "SBICARD", "CREDITACC", "UJJIVANSFB", "EQUITASBNK",
    "IRCTC", "IRFC", "RVNL", "CONCOR", "GESHIP", "SCI", "BLUEDART",
    "INDIGO", "SPICEJET", "ADANIPORTS", "GMRAIRPORT", "ATGL",
    "TATAPOWER", "TORNTPOWER", "CESC", "NLCINDIA", "SJVN", "NHPC",
    "PETRONET", "IGL", "MGL", "GUJGASLTD", "GSPL",
    "PAGEIND", "COLPAL", "DABUR", "MARICO", "GODREJCP", "EMAMILTD",
    "BRITANNIA", "NESTLEIND", "TATACONSUM", "VBL", "UBL", "RADICO",
    "MCX", "CDSL", "BSE", "CAMS", "KFINTECH", "ANGELONE", "IIFL",
    "MOTILALOFS", "NUVAMA", "HDFCAMC", "NAM-INDIA", "UTIAMC",
]


def _get(url: str, params: Optional[dict] = None, retries: int = 2) -> Optional[dict]:
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.6 * (attempt + 1))
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return None


def get_index_constituents(index_key: str = "NIFTY100") -> List[Dict]:
    """
    Returns list of dicts with ticker, name, sid for the given index.
    Falls back gracefully when API returns null.
    """
    sid = INDEX_SIDS.get(index_key)
    if not sid:
        return []

    url = f"https://api.tickertape.in/indices/constituents/{sid}"
    data = _get(url)

    if not data or not data.get("data"):
        return []

    constituents = data["data"].get("constituents") or []
    result = []
    for c in constituents:
        info = c.get("info") or c
        ticker = info.get("ticker") or info.get("symbol")
        if not ticker:
            continue
        result.append(
            {
                "ticker": ticker.upper().replace(".NS", ""),
                "name": info.get("name") or info.get("company") or ticker,
                "sid": info.get("sid"),
                "slug": info.get("slug"),
                "sector": (c.get("sector") or {}).get("name") if isinstance(c.get("sector"), dict) else c.get("sector"),
            }
        )
    return result


def get_midcap_fallback() -> List[Dict]:
    """Curated liquid midcap list used when Tickertape Midcap 150 endpoint is unavailable."""
    return [{"ticker": t, "name": t, "sid": None, "slug": None, "sector": None} for t in MIDCAP_FALLBACK]


def get_nifty100_and_midcap150(prefer_api: bool = True) -> pd.DataFrame:
    """
    Combined universe.
    - Tries Tickertape for Nifty 100 (usually works)
    - Uses curated Midcap list as reliable fallback for Midcap 150
    """
    rows = []

    # Nifty 100
    nifty100 = get_index_constituents("NIFTY100")
    if nifty100:
        for c in nifty100:
            c["universe"] = "Nifty 100"
            rows.append(c)
    else:
        # Minimal Nifty 100 style fallback (large caps)
        large = [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC",
            "SBIN", "LT", "KOTAKBANK", "AXISBANK", "HINDUNILVR", "BAJFINANCE",
            "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "ASIANPAINT",
            "TATAMOTORS", "M&M", "NTPC", "POWERGRID", "TATASTEEL", "JSWSTEEL",
            "ADANIENT", "ADANIPORTS", "ONGC", "COALINDIA", "WIPRO", "HCLTECH",
            "TECHM", "BAJAJFINSV", "DRREDDY", "CIPLA", "DIVISLAB", "GRASIM",
            "BRITANNIA", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "HINDALCO",
            "INDUSINDBK", "SBILIFE", "HDFCLIFE", "BPCL", "APOLLOHOSP", "TATACONSUM",
        ]
        for t in large:
            rows.append({"ticker": t, "name": t, "sid": None, "slug": None, "sector": None, "universe": "Nifty 100"})

    # Midcap (prefer curated for reliability + speed)
    mid = get_midcap_fallback()
    for c in mid:
        c["universe"] = "Nifty Midcap 150"
        rows.append(c)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ticker"] = df["ticker"].str.upper().str.replace(".NS", "", regex=False)
    df = df.drop_duplicates(subset=["ticker"], keep="first")
    return df.reset_index(drop=True)
