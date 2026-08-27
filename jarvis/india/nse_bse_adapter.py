"""
JARVIS AI 4.0 — Live NSE / BSE Market-Data Adapter (free public endpoints).

Wires REAL Indian market data from public sources:
  * NSE equity / index quotes + historical candles (requires session cookie).
  * NSE option-chain (real OI / IV / greeks feed) for GEX/dealer-flow.
  * BSE quotes via api.bseindia.com.

All functions are FAIL-SAFE: they return None on any network/parsing error so the
calling engine transparently falls back to synthetic data (flagged accordingly).
"""
from typing import Dict, Any, Optional, List
import logging
import time
import datetime as _dt

logger = logging.getLogger("JARVIS_NSE_BSE")

try:
    import requests
    _HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    _HAVE_REQUESTS = False

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

_TIMEOUT = 8
_SESSION_CACHE: Dict[str, Any] = {"ts": 0.0, "session": None}

# BSE scrip codes for the liquid F&O universe (used as a secondary live source).
BSE_CODE_MAP = {
    "RELIANCE": "500325", "TCS": "532540", "HDFCBANK": "500180", "ICICIBANK": "532174",
    "INFY": "500209", "BHARTIARTL": "532454", "SBIN": "500112", "MARUTI": "532500",
    "BAJFINANCE": "500034", "LT": "500510", "SUNPHARMA": "524715", "TITAN": "500114",
    "ADANIENT": "532921", "TATASTEEL": "500470", "AXISBANK": "532215", "WIPRO": "507685",
    "HCLTECH": "532281", "KOTAKBANK": "500247", "ITC": "500875", "ONGC": "500312",
}


def _nse_session() -> Optional["requests.Session"]:
    """Return a requests Session with a valid NSE cookie, caching for 60s."""
    if not _HAVE_REQUESTS:
        return None
    cache = _SESSION_CACHE
    if cache.get("session") is not None and (time.time() - cache["ts"]) < 60:
        return cache["session"]
    try:
        s = requests.Session()
        s.headers.update(_NSE_HEADERS)
        s.get("https://www.nseindia.com/", timeout=_TIMEOUT)
        cache["session"] = s
        cache["ts"] = time.time()
        return s
    except Exception as e:
        logger.warning("NSE session init failed: %s", e)
        return None


def fetch_nse_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Live NSE equity/index last price + day stats. Returns None on failure."""
    if not _HAVE_REQUESTS:
        return None
    s = _nse_session()
    if s is None:
        return None
    sym = symbol.upper().strip()
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={sym}"
        r = s.get(url, timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        j = r.json()
        price_info = j.get("priceInfo", {})
        last = price_info.get("lastPrice")
        if last is None:
            return None
        return {
            "source": "live",
            "exchange": "NSE",
            "symbol": sym,
            "last_price": float(last),
            "previous_close": float(price_info.get("previousClose", last)),
            "open": float(price_info.get("open", last)),
            "high": float(price_info.get("intraDayHighLow", {}).get("max", last)),
            "low": float(price_info.get("intraDayHighLow", {}).get("min", last)),
            "change_pct": float(price_info.get("change", {}).get("pChange", 0.0) if isinstance(price_info.get("change"), dict) else 0.0),
            "volume": int(j.get("securityWiseDP", {}).get("quantityTraded", 0) or 0),
        }
    except Exception as e:
        logger.warning("NSE quote fetch failed for %s: %s", sym, e)
        return None


def fetch_nse_historical(symbol: str, days: int = 180) -> Optional[List[Dict[str, float]]]:
    """Live NSE daily candles (date, open, high, low, close, volume). None on failure."""
    if not _HAVE_REQUESTS:
        return None
    s = _nse_session()
    if s is None:
        return None
    sym = symbol.upper().strip()
    end = _dt.date.today()
    start = end - _dt.timedelta(days=int(days * 1.6))
    try:
        url = ("https://www.nseindia.com/api/historical/cm/equity?"
               f"symbol={sym}&from={start.isoformat()}&to={end.isoformat()}&series=[%22EQ%22]")
        r = s.get(url, timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        j = r.json()
        rows = j.get("data", [])
        out = []
        for row in rows:
            try:
                out.append({
                    "date": row.get("CH_TIMESTAMP") or row.get("TIMESTAMP"),
                    "open": float(row["CH_OPENING_PRICE"]),
                    "high": float(row["CH_TRADE_HIGH_PRICE"]),
                    "low": float(row["CH_TRADE_LOW_PRICE"]),
                    "close": float(row["CH_CLOSING_PRICE"]),
                    "volume": int(row.get("CH_TOT_TRADED_QTY", 0) or 0),
                })
            except Exception:
                continue
        return out if len(out) >= 30 else None
    except Exception as e:
        logger.warning("NSE historical fetch failed for %s: %s", sym, e)
        return None


def fetch_nse_option_chain(symbol: str) -> Optional[Dict[str, Any]]:
    """Live NSE option chain (indices use option-chain-indices, equities option-chain-equities)."""
    if not _HAVE_REQUESTS:
        return None
    s = _nse_session()
    if s is None:
        return None
    sym = symbol.upper().strip()
    try:
        # try index endpoint first, fall back to equity
        for ep in ("option-chain-indices", "option-chain-equities"):
            url = f"https://www.nseindia.com/api/{ep}?symbol={sym}"
            r = s.get(url, timeout=_TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                rec = j.get("records")
                if rec:
                    return _normalize_nse_chain(j, symbol)
        return None
    except Exception as e:
        logger.warning("NSE option chain fetch failed for %s: %s", sym, e)
        return None


def _normalize_nse_chain(j: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    rec = j["records"]
    underlying = float(rec.get("underlyingValue", 0.0))
    exp = rec.get("expiryDates", [""])[0]
    out_rows = []
    for item in rec.get("data", []):
        if item.get("expiryDate") != exp:
            continue
        ce = item.get("CE", {}) or {}
        pe = item.get("PE", {}) or {}
        if not ce and not pe:
            continue
        out_rows.append({
            "strike": float(item.get("strikePrice", 0.0)),
            "call": {
                "oi": int(ce.get("openInterest", 0) or 0),
                "oi_change_pct": float(ce.get("pchangeinOpenInterest", 0) or 0.0),
                "change_pct": float(ce.get("pChange", 0.0) or 0.0),
                "volume": int(ce.get("totalTradedVolume", 0) or 0),
                "iv": float(ce.get("impliedVolatility", 0.0) or 0.0),
                "ltp": float(ce.get("lastPrice", 0.0) or 0.0),
                "delta": float(ce.get("delta", 0.0) or 0.0),
                "gamma": float(ce.get("gamma", 0.0) or 0.0),
                "theta": float(ce.get("theta", 0.0) or 0.0),
                "vega": float(ce.get("vega", 0.0) or 0.0),
            },
            "put": {
                "oi": int(pe.get("openInterest", 0) or 0),
                "oi_change_pct": float(pe.get("pchangeinOpenInterest", 0) or 0.0),
                "change_pct": float(pe.get("pChange", 0.0) or 0.0),
                "volume": int(pe.get("totalTradedVolume", 0) or 0),
                "iv": float(pe.get("impliedVolatility", 0.0) or 0.0),
                "ltp": float(pe.get("lastPrice", 0.0) or 0.0),
                "delta": float(pe.get("delta", 0.0) or 0.0),
                "gamma": float(pe.get("gamma", 0.0) or 0.0),
                "theta": float(pe.get("theta", 0.0) or 0.0),
                "vega": float(pe.get("vega", 0.0) or 0.0),
            },
        })
    return {
        "data_source": "live",
        "symbol": symbol.upper(),
        "spot_price": underlying,
        "expiry": exp,
        "chain": out_rows,
    }


def fetch_bse_quote(bse_code: str) -> Optional[Dict[str, Any]]:
    """Live BSE quote by scrip code (e.g. 500325 for RELIANCE). None on failure."""
    if not _HAVE_REQUESTS:
        return None
    code = str(bse_code).strip()
    try:
        url = f"https://api.bseindia.com/Bse_data/json/GetQuote.aspx?Type=EQ&Code={code}"
        r = requests.get(url, headers=_BSE_HEADERS, timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        j = r.json()
        if isinstance(j, list) and j:
            q = j[0]
        elif isinstance(j, dict):
            q = j
        else:
            return None
        last = q.get("LTP") or q.get("lastPrice") or q.get("PrevClose")
        if last is None:
            return None
        return {
            "source": "live",
            "exchange": "BSE",
            "bse_code": code,
            "last_price": float(last),
            "previous_close": float(q.get("PrevClose", last)),
            "open": float(q.get("Open", last)),
            "high": float(q.get("High", last)),
            "low": float(q.get("Low", last)),
            "change_pct": float(q.get("ChangePct", 0.0) or 0.0),
            "volume": int(float(q.get("Volume", 0) or 0)),
            "name": q.get("CompanyName", ""),
        }
    except Exception as e:
        logger.warning("BSE quote fetch failed for %s: %s", code, e)
        return None


def fetch_live_india_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Try NSE first, then fall back to BSE for the given Indian symbol."""
    q = fetch_nse_quote(symbol)
    if q:
        return q
    code = BSE_CODE_MAP.get(symbol.upper().strip())
    if code:
        return fetch_bse_quote(code)
    return None
