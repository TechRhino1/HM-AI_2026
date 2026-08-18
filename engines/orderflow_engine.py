import numpy as np
import pandas as pd
from typing import Dict, Any, List

class InstitutionalVolumeOrderFlowEngine:
    def __init__(self, logger: Any = None):
        self.logger = logger

    def calculate_volume_profile(self, df: pd.DataFrame, num_bins: int = 30) -> Dict[str, Any]:
        """
        Calculates Institutional Volume Profile:
        - Point of Control (POC): Highest volume concentration price level.
        - Value Area High (VAH): Upper 70% volume boundary.
        - Value Area Low (VAL): Lower 70% volume boundary.
        """
        if len(df) < 20 or "volume" not in df.columns:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "hvn_nodes": [], "lvn_nodes": []}

        min_p = float(df["low"].min())
        max_p = float(df["high"].max())
        if max_p <= min_p:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "hvn_nodes": [], "lvn_nodes": []}

        bins = np.linspace(min_p, max_p, num_bins + 1)
        bin_volumes = np.zeros(num_bins)

        for _, row in df.iterrows():
            c_price = (row["high"] + row["low"]) / 2.0
            vol = row["volume"]
            bin_idx = int(np.clip(np.digitize(c_price, bins) - 1, 0, num_bins - 1))
            bin_volumes[bin_idx] += vol

        poc_idx = int(np.argmax(bin_volumes))
        poc_price = float((bins[poc_idx] + bins[poc_idx + 1]) / 2.0)

        # Calculate 70% Value Area
        total_vol = float(np.sum(bin_volumes))
        target_va_vol = total_vol * 0.70

        sorted_indices = np.argsort(bin_volumes)[::-1]
        accum_vol = 0.0
        va_bins = []
        for idx in sorted_indices:
            accum_vol += bin_volumes[idx]
            va_bins.append(idx)
            if accum_vol >= target_va_vol:
                break

        val_bin = min(va_bins)
        vah_bin = max(va_bins)

        val_price = float(bins[val_bin])
        vah_price = float(bins[vah_bin + 1])

        # High Volume Nodes (HVN) & Low Volume Nodes (LVN)
        vol_mean = np.mean(bin_volumes)
        hvn_nodes = [float((bins[i] + bins[i+1])/2.0) for i in range(num_bins) if bin_volumes[i] > vol_mean * 1.5]
        lvn_nodes = [float((bins[i] + bins[i+1])/2.0) for i in range(num_bins) if bin_volumes[i] < vol_mean * 0.4]

        return {
            "poc": round(poc_price, 2),
            "vah": round(vah_price, 2),
            "val": round(val_price, 2),
            "hvn_nodes": [round(x, 2) for x in hvn_nodes],
            "lvn_nodes": [round(x, 2) for x in lvn_nodes]
        }

    def analyze_order_flow_imbalance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes Cumulative Volume Delta (CVD) & Bar Order Flow Imbalance.
        Determines whether Institutional Buying or Selling Pressure dominates.
        """
        if len(df) < 15:
            return {"delta_imbalance": "NEUTRAL", "buy_vol_ratio": 0.5, "cvd_trend": "FLAT"}

        df_copy = df.copy()
        # Estimate Buy vs Sell Volume via Candle Position (Price Action Delta Proxy)
        range_span = df_copy["high"] - df_copy["low"] + 1e-9
        close_pos = (df_copy["close"] - df_copy["low"]) / range_span

        buy_vol = df_copy["volume"] * close_pos
        sell_vol = df_copy["volume"] * (1.0 - close_pos)

        delta = buy_vol - sell_vol
        cvd = delta.cumsum()

        recent_buy_ratio = float(buy_vol.tail(5).sum() / (df_copy["volume"].tail(5).sum() + 1e-9))
        cvd_recent_slope = float(cvd.iloc[-1] - cvd.iloc[-5])

        if recent_buy_ratio >= 0.62 and cvd_recent_slope > 0:
            imbalance = "BULLISH_ORDER_FLOW"
        elif recent_buy_ratio <= 0.38 and cvd_recent_slope < 0:
            imbalance = "BEARISH_ORDER_FLOW"
        else:
            imbalance = "NEUTRAL"

        return {
            "delta_imbalance": imbalance,
            "buy_vol_ratio": round(recent_buy_ratio, 2),
            "cvd_slope": round(cvd_recent_slope, 2),
            "cvd_trend": "BULLISH" if cvd_recent_slope > 0 else ("BEARISH" if cvd_recent_slope < 0 else "FLAT")
        }

    def detect_liquidity_sweeps(self, df: pd.DataFrame, swing_highs: List[float], swing_lows: List[float]) -> Dict[str, Any]:
        """
        Detects Institutional Liquidity Sweeps (BSL/SSL Stop Hunts) at Key Support & Resistance:
        - Buy-Side Liquidity (BSL) Sweep: Candle wick pierces swing high and aggressively closes back inside range.
        - Sell-Side Liquidity (SSL) Sweep: Candle wick pierces swing low and aggressively closes back inside range.
        """
        if len(df) < 5:
            return {"sweep_detected": False, "sweep_type": "NONE", "sweep_level": 0.0}

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        c_open, c_close, c_high, c_low = float(latest["open"]), float(latest["close"]), float(latest["high"]), float(latest["low"])
        c_range = c_high - c_low + 1e-9

        # SSL Sweep (Sell-Side Liquidity Hunt below Support)
        for s_low in swing_lows[-3:]:
            if c_low < s_low and c_close > s_low:
                upper_wick = c_high - max(c_open, c_close)
                lower_wick = min(c_open, c_close) - c_low
                if lower_wick / c_range >= 0.45:  # Strong rejection lower wick
                    return {
                        "sweep_detected": True,
                        "sweep_type": "BULLISH_SSL_SWEEP",
                        "sweep_level": round(s_low, 2),
                        "rejection_wick_ratio": round(lower_wick / c_range, 2)
                    }

        # BSL Sweep (Buy-Side Liquidity Hunt above Resistance)
        for s_high in swing_highs[-3:]:
            if c_high > s_high and c_close < s_high:
                upper_wick = c_high - max(c_open, c_close)
                if upper_wick / c_range >= 0.45:  # Strong rejection upper wick
                    return {
                        "sweep_detected": True,
                        "sweep_type": "BEARISH_BSL_SWEEP",
                        "sweep_level": round(s_high, 2),
                        "rejection_wick_ratio": round(upper_wick / c_range, 2)
                    }

        return {"sweep_detected": False, "sweep_type": "NONE", "sweep_level": 0.0}
