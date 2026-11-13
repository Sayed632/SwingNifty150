# SwingNifty150

**Swing Trade Scanner for Nifty 100 + Nifty Midcap 150**

A clean Streamlit application that:

- Fetches index constituents (Tickertape public endpoints)
- Analyzes daily candles (RSI, MACD, Bollinger Bands, ATR, EMAs)
- Calculates Beta vs Nifty 50
- Generates Entry / Stop-Loss / Target levels (ATR-based)
- Includes a risk-based Position Size Calculator
- Shows interactive Plotly charts

## Quick Start (Local)

```bash
git clone https://github.com/Sayed632/SwingNifty150.git
cd SwingNifty150

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect the repository `Sayed632/SwingNifty150`
3. Main file: `app.py`
4. Deploy

## Features

| Feature | Details |
|---------|---------|
| Universe | Nifty 100 + Nifty Midcap 150 |
| Filters | Beta range, RSI range, minimum bullish score |
| Signals | STRONG BUY / BUY / WATCH / AVOID |
| Levels | Entry, Stop-Loss (1.5×ATR), Target 1 (2×ATR), Target 2 (3×ATR) |
| Position Sizing | Risk % of capital → quantity & max loss |
| Charts | Candlestick + EMA + Bollinger + RSI + MACD |

## Disclaimer

This tool is for **educational and research purposes only**.  
It is **not** investment advice. Always do your own due diligence and risk management.

## License

MIT

## Daily Pre-computation (GitHub Actions)

A scheduled workflow runs every weekday at **~4:15 PM IST** (after market close):

- Scans the full Nifty 100 + Midcap universe
- Saves results to `data/cache/latest_scan.json`
- Commits the cache back to the repo

The Streamlit app loads this cache by default → **instant results**.

### Manual trigger
1. Go to the repo **Actions** tab
2. Select **Daily Swing Scan**
3. Click **Run workflow**

### Force live scan
In the app sidebar, check **Force live scan** if you want fresh data outside the daily window.
