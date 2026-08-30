"""
Real market-data provider for MT5 broker feeds, India (NSE/BSE), and global equities.

The India/Stocks analytical engines must never silently present fabricated
price history as if it were real. This module centralises the attempt to fetch
genuine OHLCV candles from a live source. When no live source is available
(e.g. MT5 is unavailable, yfinance is not installed, or there is no network
connectivity), it returns ``None`` so the caller can fall back to a clearly
labelled synthetic generator.

Live sources (attempted in order):
  1. `MetaTrader5` (MT5) — real-time broker prices & tick volume for US/global equities.
  2. `yfinance`  — free, no API key; covers NSE/BSE indices & equities
                   (e.g. ``^NSEI``, ``RELIANCE.NS``) and US equities
                   (e.g. ``AAPL``). This is the practical substitute for a
                   TradingView/Indian exchange feed in environments without a
                   broker data entitlement.
"""
from typing import Optional, List, Dict, Any
import logging
import socket
import re
import datetime as _dt

logger = logging.getLogger("jarvis.market_data")

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

_TF_TO_YF = {
    "1M": "1m", "5M": "5m", "15M": "15m", "30M": "30m",
    "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1wk", "1MO": "1mo",
}

_TF_TO_MT5 = {
    "1M": getattr(mt5, "TIMEFRAME_M1", 1) if (MT5_AVAILABLE and mt5) else 1,
    "M1": getattr(mt5, "TIMEFRAME_M1", 1) if (MT5_AVAILABLE and mt5) else 1,
    "5M": getattr(mt5, "TIMEFRAME_M5", 5) if (MT5_AVAILABLE and mt5) else 5,
    "M5": getattr(mt5, "TIMEFRAME_M5", 5) if (MT5_AVAILABLE and mt5) else 5,
    "15M": getattr(mt5, "TIMEFRAME_M15", 15) if (MT5_AVAILABLE and mt5) else 15,
    "M15": getattr(mt5, "TIMEFRAME_M15", 15) if (MT5_AVAILABLE and mt5) else 15,
    "30M": getattr(mt5, "TIMEFRAME_M30", 30) if (MT5_AVAILABLE and mt5) else 30,
    "M30": getattr(mt5, "TIMEFRAME_M30", 30) if (MT5_AVAILABLE and mt5) else 30,
    "1H": getattr(mt5, "TIMEFRAME_H1", 16385) if (MT5_AVAILABLE and mt5) else 16385,
    "H1": getattr(mt5, "TIMEFRAME_H1", 16385) if (MT5_AVAILABLE and mt5) else 16385,
    "4H": getattr(mt5, "TIMEFRAME_H4", 16388) if (MT5_AVAILABLE and mt5) else 16388,
    "H4": getattr(mt5, "TIMEFRAME_H4", 16388) if (MT5_AVAILABLE and mt5) else 16388,
    "1D": getattr(mt5, "TIMEFRAME_D1", 16408) if (MT5_AVAILABLE and mt5) else 16408,
    "D1": getattr(mt5, "TIMEFRAME_D1", 16408) if (MT5_AVAILABLE and mt5) else 16408,
    "1W": getattr(mt5, "TIMEFRAME_W1", 32769) if (MT5_AVAILABLE and mt5) else 32769,
    "W1": getattr(mt5, "TIMEFRAME_W1", 32769) if (MT5_AVAILABLE and mt5) else 32769,
    "1MO": getattr(mt5, "TIMEFRAME_MN1", 49153) if (MT5_AVAILABLE and mt5) else 49153,
    "MN1": getattr(mt5, "TIMEFRAME_MN1", 49153) if (MT5_AVAILABLE and mt5) else 49153,
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

_COMMON_STOCK_ALIASES = {
    "GOOGL": "Google",
    "GOOG": "Google",
    "META": "Facebook",
    "FB": "Facebook",
    "AMD": "AdvMicroDev",
    "DIS": "Disney",
    "AAPL": "Apple",
    "NVDA": "Nvidia",
    "TSLA": "Tesla",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "NFLX": "Netflix",
    "PLTR": "Palantir",
    "COIN": "Coinbase",
    "UBER": "Uber",
    "BA": "Boeing",
    "INTC": "Intel",
    "AVGO": "Broadcom",
    "TSM": "Taiwan-Semiconductor",
    "ARM": "Arm Holdings",
    "SMCI": "Super Micro Computer",
    "MU": "Micron",
    "QCOM": "Qualcomm",
    "PANW": "PaloAltoNetworks",
    "CRM": "Salesforce",
    "SHOP": "Shopify",
    "LLY": "EliLilly",
    "JNJ": "J&J",
    "UNH": "UnitedHealth",
    "JPM": "JPMorgan",
    "V": "Visa",
    "BAC": "BofAmerica",
    "XOM": "ExxonMobil",
    "CVX": "Chevron",
    "CAT": "Caterpillar",
    "WMT": "WalMart",
    "COST": "Costco",
    "NIO": "NIO",
    "RIVN": "Rivian",
    "LCID": "LucidGroup",
    "XPEV": "Xpeng",
    "LI": "LiAuto",
    "HOOD": "Robinhood",
    "SOFI": "SoFiTechnologies",
    "CRWD": "Crowdstrike",
    "BABA": "Alibaba",
}

_DESC_PATTERN = re.compile(r'\(([A-Z0-9]+)(?:\.[A-Z]+)?\)')
_MT5_RESOLVED_CACHE: Dict[str, Optional[str]] = {}
_MT5_SYMBOL_MAP: Dict[str, str] = {}
_MT5_INDEX_BUILT: bool = False


def _ensure_mt5_connected() -> bool:
    """Check if MT5 is connected or initialize connection if available."""
    if not MT5_AVAILABLE or mt5 is None:
        return False
    try:
        t_info = mt5.terminal_info()
        if t_info is not None and getattr(t_info, "connected", False):
            return True
        return bool(mt5.initialize())
    except Exception as exc:
        logger.debug("MT5 connection check failed: %s", exc)
        return False


def _build_mt5_symbol_index():
    global _MT5_INDEX_BUILT
    if not _ensure_mt5_connected():
        return
    symbols = mt5.symbols_get()
    if not symbols:
        return
    for s in symbols:
        name = s.name
        desc = s.description or ""
        m = _DESC_PATTERN.search(desc)
        if m:
            ticker = m.group(1).upper()
            if ticker not in _MT5_SYMBOL_MAP:
                _MT5_SYMBOL_MAP[ticker] = name
        s_u = name.upper()
        if s_u not in _MT5_SYMBOL_MAP:
            _MT5_SYMBOL_MAP[s_u] = name
    _MT5_INDEX_BUILT = True


def _resolve_mt5_symbol(symbol: str) -> Optional[str]:
    """Dynamically resolve stock ticker to MT5 broker symbol."""
    ticker = symbol.strip().upper()
    if ticker in _MT5_RESOLVED_CACHE:
        return _MT5_RESOLVED_CACHE[ticker]

    if not _ensure_mt5_connected():
        return None

    if not _MT5_INDEX_BUILT:
        _build_mt5_symbol_index()

    # 1. Direct match from regex-parsed descriptions
    if ticker in _MT5_SYMBOL_MAP:
        cand = _MT5_SYMBOL_MAP[ticker]
        if mt5.symbol_info(cand) is not None:
            _MT5_RESOLVED_CACHE[ticker] = cand
            return cand

    # 2. Direct match s.name.upper() == ticker or ticker + "#" or ticker + ".US"
    for suffix in ("", "#", ".US", ".C", "M"):
        key = f"{ticker}{suffix}"
        if key in _MT5_SYMBOL_MAP:
            cand = _MT5_SYMBOL_MAP[key]
            if mt5.symbol_info(cand) is not None:
                _MT5_RESOLVED_CACHE[ticker] = cand
                return cand
        info = mt5.symbol_info(key)
        if info is not None:
            _MT5_RESOLVED_CACHE[ticker] = info.name
            return info.name

    # 3. Common alias dictionary fallback
    if ticker in _COMMON_STOCK_ALIASES:
        cand = _COMMON_STOCK_ALIASES[ticker]
        if mt5.symbol_info(cand) is not None:
            _MT5_RESOLVED_CACHE[ticker] = cand
            return cand

    # 4. Direct scan across all symbols if index missed something
    all_syms = mt5.symbols_get() or []
    for s in all_syms:
        desc = s.description or ""
        m = _DESC_PATTERN.search(desc)
        if m and m.group(1).upper() == ticker:
            _MT5_RESOLVED_CACHE[ticker] = s.name
            return s.name
        s_u = s.name.upper()
        if s_u == ticker or s_u == f"{ticker}#" or s_u == f"{ticker}.US":
            _MT5_RESOLVED_CACHE[ticker] = s.name
            return s.name

    _MT5_RESOLVED_CACHE[ticker] = None
    return None


def _try_mt5(symbol: str, timeframe: str = "1D", num_bars: int = 120) -> Optional[List[Dict[str, Any]]]:
    """High-performance MT5 symbol resolver and rate fetcher."""
    if not MT5_AVAILABLE or mt5 is None:
        return None
    try:
        if not _ensure_mt5_connected():
            return None

        resolved_sym = _resolve_mt5_symbol(symbol)
        if not resolved_sym:
            return None

        # Select symbol in MarketWatch
        mt5.symbol_select(resolved_sym, True)

        mt5_tf = _TF_TO_MT5.get(timeframe.upper(), getattr(mt5, "TIMEFRAME_D1", 16408))
        rates = mt5.copy_rates_from_pos(resolved_sym, mt5_tf, 0, num_bars)
        if rates is None or len(rates) == 0:
            return None

        candles: List[Dict[str, Any]] = []
        for r in rates:
            vol = int(r["tick_volume"]) if r["tick_volume"] > 0 else int(r["real_volume"])
            candles.append({
                "time": int(r["time"]),
                "open": round(float(r["open"]), 4),
                "high": round(float(r["high"]), 4),
                "low": round(float(r["low"]), 4),
                "close": round(float(r["close"]), 4),
                "volume": vol,
            })
        return candles if candles else None
    except Exception as exc:
        logger.warning("MT5 fetch failed for %s: %s", symbol, exc)
        return None


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


def _try_nse(symbol: str, timeframe: str, num_bars: int) -> Optional[List[Dict[str, Any]]]:
    """Live NSE daily candles (real exchange data). Intraday not provided by the
    free endpoint, so only Daily/Weekly/Monthly timeframes are served."""
    if timeframe.upper() not in ("1D", "1W", "1MO", "1WK"):
        return None
    try:
        from jarvis.india.nse_bse_adapter import fetch_nse_historical
    except Exception:
        return None
    rows = fetch_nse_historical(symbol, days=num_bars)
    if not rows:
        return None
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            ts = r.get("date")
            if isinstance(ts, str):
                ts = int(_dt.datetime.strptime(ts, "%Y-%m-%d").timestamp())
            elif hasattr(ts, "timestamp"):
                ts = int(ts.timestamp())
            else:
                ts = int(ts) if ts else 0
            out.append({
                "time": ts,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r.get("volume", 0) or 0),
            })
        except Exception:
            continue
    out = out[-num_bars:]
    return out if out else None


def _try_tradingview(symbol: str, timeframe: str = "1D", num_bars: int = 120) -> Optional[List[Dict[str, Any]]]:
    """Attempt to fetch live candles via TradingView scanner and real-time feeds."""
    try:
        from jarvis.data.tradingview_provider import TRADINGVIEW_PROVIDER
        return TRADINGVIEW_PROVIDER.fetch_candles(symbol, timeframe=timeframe, num_bars=num_bars)
    except Exception as exc:
        logger.debug("TradingView fetch failed for %s: %s", symbol, exc)
        return None


def get_calibrated_baseline_candles(
    symbol: str, timeframe: str = "1D", num_bars: int = 120, market: str = "US"
) -> List[Dict[str, Any]]:
    """Tier 4 graceful fallback: generates geometrically bounded candle series
    anchored to 2026 calibrated baseline prices when all live feeds are unreachable."""
    import math
    import time
    import numpy as np

    if market == "IN":
        try:
            from jarvis.india.universe import get_india_profile
            prof = get_india_profile(symbol)
            base_p = float(prof.get("base_price", 1000.0))
            beta_v = 1.0
        except Exception:
            base_p = 1000.0
            beta_v = 1.0
    else:
        try:
            from jarvis.stocks.universe import get_stock_profile
            prof = get_stock_profile(symbol)
            base_p = float(prof.get("base_price", 150.0))
            beta_v = float(prof.get("beta", 1.2))
        except Exception:
            base_p = 150.0
            beta_v = 1.2

    tf_sec = _TF_TO_MT5.get(timeframe.upper(), 86400)
    if isinstance(tf_sec, int) and tf_sec > 10000:
        step_sec = 86400 if tf_sec == 16408 else (604800 if tf_sec == 32769 else 2592000)
    else:
        step_sec = int(tf_sec) if isinstance(tf_sec, int) and tf_sec < 10000 else 86400

    now_ts = int(time.time())
    vol_scalar = max(0.003, min(0.015 * beta_v * math.sqrt(step_sec / 86400.0), 0.045))
    seed = int(abs(hash(f"{symbol}_{timeframe}_{now_ts // 3600}"))) % (2**32)
    rng = np.random.RandomState(seed)

    returns = rng.normal(loc=0.0003, scale=vol_scalar, size=num_bars)
    prices = base_p * np.exp(np.cumsum(returns))
    scale_factor = base_p / prices[-1]
    prices *= scale_factor

    candles: List[Dict[str, Any]] = []
    for i in range(num_bars):
        bar_time = now_ts - (num_bars - 1 - i) * step_sec
        c = float(prices[i])
        prev_c = float(prices[i - 1]) if i > 0 else c * (1.0 - returns[0])
        o = prev_c + float(rng.normal(0, c * vol_scalar * 0.2))
        h = max(o, c) + abs(float(rng.normal(0, c * vol_scalar * 0.7)))
        l = min(o, c) - abs(float(rng.normal(0, c * vol_scalar * 0.7)))
        v = int(1000000 * beta_v * rng.uniform(0.7, 1.5))
        candles.append({
            "time": bar_time,
            "open": round(float(o), 4),
            "high": round(float(h), 4),
            "low": round(float(l), 4),
            "close": round(float(c), 4),
            "volume": v,
        })
    return candles


def fetch_real_candles(
    symbol: str,
    timeframe: str = "1D",
    num_bars: int = 120,
    market: str = "US",
) -> Optional[List[Dict[str, Any]]]:
    """Attempt to fetch genuine OHLCV candles across the multi-tier data hierarchy.

    Hierarchy:
      Tier 1: MT5 live broker feed
      Tier 2: TradingView Scanner real-time feed
      Tier 3: yfinance free exchange feed
      Tier 4: Callers fallback to 2026 calibrated baseline prices.

    Returns a list of candle dicts (newest last) or ``None`` when no live
    source is reachable.
    """
    # Indian equities/indices: prefer the real NSE feed, then TradingView, then yfinance.
    if market == "IN":
        candles = _try_nse(symbol, timeframe, num_bars)
        if candles:
            logger.info("Live NSE candles for %s (%d bars)", symbol, len(candles))
            return candles

        candles = _try_tradingview(symbol, timeframe, num_bars)
        if candles:
            logger.info("Live TradingView candles for %s (%d bars)", symbol, len(candles))
            return candles

        ticker = _resolve_ticker(symbol, market)
        candles = _try_yfinance(ticker, timeframe, num_bars)
        if candles:
            logger.info("Live candles for %s (ticker=%s, %d bars)", symbol, ticker, len(candles))
            return candles
        return None

    # US / Global equities:
    # Tier 1: MT5 live broker feed
    candles = _try_mt5(symbol, timeframe=timeframe, num_bars=num_bars)
    if candles:
        logger.info("Live MT5 candles for %s (%d bars)", symbol, len(candles))
        return candles

    # Tier 2: TradingView live scanner provider
    candles = _try_tradingview(symbol, timeframe=timeframe, num_bars=num_bars)
    if candles:
        logger.info("Live TradingView candles for %s (%d bars)", symbol, len(candles))
        return candles

    # Tier 3: yfinance free exchange feed
    ticker = _resolve_ticker(symbol, market)
    candles = _try_yfinance(ticker, timeframe, num_bars)
    if candles:
        logger.info("Live candles for %s (ticker=%s, %d bars)", symbol, ticker, len(candles))
        return candles

    return None
