# Rocket — Stock Scanner

Rocket is a technical stock scanner: a data pipeline (yfinance / CoinGecko / OpenAvanza),
an evidence-weighted **Rocket score**, a Dash dashboard, a CLI, and a Telegram bot. This
repository holds the scanner engine and a hosted, read-only demo of its output.

## The Rocket score

For each ticker the engine runs **29 technical indicators** across four families and folds
them into a single evidence-weighted score:

| Family | Indicators | Examples |
|--------|-----------:|----------|
| Momentum   | 6  | RSI, MACD, ROC, Stochastic, Williams %R, CCI |
| Trend      | 17 | EMA crossover, ADX, EMA 9/21/50/200, Ichimoku, Supertrend, Parabolic SAR, chart patterns |
| Volatility | 3  | Bollinger Bands, ATR, Donchian Channel |
| Volume     | 3  | OBV, MFI, VWAP |

The indicators vote by family; a confidence and a risk multiplier are applied, and the
result is an **Overall score (0–100)** plus a **BUY / HOLD / SELL** signal per ticker, with
per-category sub-scores for Momentum, Trend, Volatility and Volume. The full list lives in
`rocket/scoring/rocket_score.py` (`INDICATORS`).

## The hosted page is a read-only demo snapshot

The page at **https://sibbamala.com/rocket/** is a **static, read-only snapshot** — it is
not a live scan and does not cover a global universe. Concretely, the snapshot contains:

- **35 tickers** (a fixed curated watchlist of large caps: AAPL, MSFT, SAP.DE, SAAB-B.ST, …)
- **3 regions**: Germany, Sweden, USA
- **790 daily bars** of OHLCV
- **Data as-of 2026-08-12** (the "Generated" timestamp on the page is only when the static
  HTML file was built, not a live refresh)

It is a proof-of-concept of the pipeline end to end (real prices, real scoring math, a clean
read-only UI), sized as a small sample. The snapshot's detail tab surfaces a representative
signal per category rather than all 29 indicators. It deliberately makes **no claim** of live
data, global coverage, or a full-universe scan.

## Repository layout

- `app.py`, `server.py` — the Dash dashboard (engine UI; `server.py` is the hosting entrypoint)
- `rocket/scoring/` — the Rocket score (`rocket_score.py`, weighting, risk, confidence)
- `rocket/technical/` — the 29 indicator implementations
- `rocket/data/`, `data_fetcher/` — data fetch and storage
- `rocket/telegram_bot/`, `rocket/backtest/`, `rocket/scan_engine/` — bot, backtests, scans
- `index.html` — the hosted read-only demo snapshot
- `hosting.yaml` — deployment manifest (static demo)
