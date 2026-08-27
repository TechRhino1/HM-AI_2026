"""
Real market-data provider for India (NSE/BSE) and global equities.

The India/Stocks analytical engines must never silently present fabricated
price history as if it were real. This module centralises the attempt to fetch
genuine OHLCV candles from a live source. When no live source is available
(e.g. the optional `yfinance` package is not installed, or there is no network
connectivity), it returns ``None`` so the caller can fall back to a clearly
labelled synthetic generator.

Live sources (attempted in order):
  1. `yfinance`  — free, no API key; covers NSE/BSE indices & equities
                   (e.g. ``^NSEI``, ``RELIANCE.NS``) and US equities
                   (e.g. ``AAPL``). This is the practical substitute for a
                   TradingView/Indian exchange feed in environments without a
                   broker data entitlement.
"""
from typing import Optional, List, Dict, Any
import logging
import socket

logger = logging.getLogger("jarvis.market_data")

_TF_TO_YF = {
    "1M": "1m", "5M": "5m", "15M": "15m", "30M": "30m",
    "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1wk", "1MO": "1mo",
}

_INDIA_INDEX_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY 50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "BANK NIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTYAUTO": "^CNXAUTO",
    "NIFTYIT": "^CNXIT",
    "SENSEX": "^BSESN",
}


def _resolve_ticker(symbol: str, market: str) -> str:
    s = symbol.strip().upper()
    if market == "IN":
        if s in _INDIA_INDEX_MAP:
            return _INDIA_INDEX_MAP[s]
        if s.endswith(".NS") or s.endswith(".BO"):
            return s
        if s.isalpha() and "." not in symbol:
            return f"{s}.NS"
        return s
    # US / generic
    return symbol


def _try_yfinance(ticker: str, timeframe: str, num_bars: int) -> Optional[List[Dict[str, Any]]]:
    try:
        import yfinance as yf
    except Exception:
        return None
    interval = _TF_TO_YF.get(timeframe.upper(), "1d")
    # Intraday histories are only available for a short window on Yahoo.
    period = "5d" if interval in ("1m", "5m", "15m", "30m") else "1y"
    prev_timeout = socket.getdefaulttimeout()
    try:
        # Bound the network call so a stalled connection cannot hang the engine.
        socket.setdefaulttimeout(10)
        df = yf.Ticker(ticker).history(
            period=period, interval=interval, actions=False, auto_adjust=False
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "no live data"
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return None
    finally:
        socket.setdefaulttimeout(prev_timeout)
    if df is None or len(df) == 0:
        return None
    rows: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        rows.append({
            "time": int(ts.timestamp()),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row.get("Volume", 0) or 0),
        })
    rows = rows[-num_bars:]
    return rows if rows else None


def fetch_real_candles(
    symbol: str,
    timeframe: str = "1D",
    num_bars: int = 120,
    market: str = "US",
) -> Optional[List[Dict[str, Any]]]:
    """Attempt to fetch genuine OHLCV candles.

    Returns a list of candle dicts (newest last) or ``None`` when no live
    source is reachable. Callers MUST fall back to a synthetic generator and
    flag the result as such when this returns ``None``.
    """
    ticker = _resolve_ticker(symbol, market)
    candles = _try_yfinance(ticker, timeframe, num_bars)
    if candles:
        logger.info("Live candles for %s (ticker=%s, %d bars)", symbol, ticker, len(candles))
        return candles
    return None
