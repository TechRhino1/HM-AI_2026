"""
JARVIS AI 3.0 — Strategy & Regime Performance Memory Engine.
Evaluates historical performance segmented by market regime to dynamically adjust strategy activation probabilities.
"""
from typing import Dict, List, Any
from jarvis.learning.trade_memory import TradeMemory

class StrategyRegimeMemory:
    def __init__(self, memory_db: TradeMemory):
        self.memory_db = memory_db

    def get_regime_strategy_matrix(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        trades = self.memory_db.fetch_recent_trades(100)
        if not trades:
            return {}

        # regime -> strategy -> stats
        regime_stats: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for t in trades:
            reg = t.get("regime", "UNKNOWN")
            strat = t.get("strategy", "UNKNOWN")
            
            if reg not in regime_stats:
                regime_stats[reg] = {}
            if strat not in regime_stats[reg]:
                regime_stats[reg][strat] = {"wins": 0, "losses": 0, "pnls": []}

            if t.get("is_win", 0) == 1:
                regime_stats[reg][strat]["wins"] += 1
            else:
                regime_stats[reg][strat]["losses"] += 1
            regime_stats[reg][strat]["pnls"].append(t.get("pnl", 0.0))

        result = {}
        for reg, strats in regime_stats.items():
            result[reg] = {}
            for strat, data in strats.items():
                total = data["wins"] + data["losses"]
                win_rate = (data["wins"] / total * 100.0) if total > 0 else 0.0
                gross_win = sum(p for p in data["pnls"] if p > 0)
                gross_loss = abs(sum(p for p in data["pnls"] if p < 0))
                pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 1.0)

                result[reg][strat] = {
                    "total_trades": total,
                    "win_rate_pct": round(win_rate, 1),
                    "profit_factor": round(pf, 2),
                    "net_pnl": round(sum(data["pnls"]), 2),
                    "status": "ACTIVE" if (pf >= 1.2 and win_rate >= 50.0) or total < 5 else "DEGRADED"
                }

        return result
