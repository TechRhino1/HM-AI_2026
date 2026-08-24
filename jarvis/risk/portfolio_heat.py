"""
JARVIS AI 4.0 — Portfolio Heat & Stress Measurement Engine.
Calculates a real-time standardized Portfolio Heat score (0–100) combining open monetary risk,
floating drawdown, margin utilization, active position density, and cross-asset correlation stress.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from jarvis.data.schemas import PositionSnapshot, AccountSnapshot

logger = logging.getLogger("JARVIS_PortfolioHeat")

@dataclass
class PortfolioHeatResult:
    score: float                      # 0.0 to 100.0
    zone: str                         # "NORMAL", "MODERATE", "HIGH", "EXTREME"
    risk_multiplier: float            # 1.0, 0.75, 0.50, 0.0
    allow_new_risk: bool              # False if score >= 85.0
    allow_same_symbol_addition: bool  # False if score >= 70.0
    components: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

class PortfolioHeatEngine:
    """
    Computes unified portfolio heat (0-100).
    Thresholds:
      0 - 49.9:  NORMAL   -> Full 1.0x sizing, standard operations
      50 - 69.9: MODERATE -> 0.75x risk sizing, same-symbol additions permitted if conditions pass
      70 - 84.9: HIGH     -> 0.50x risk sizing, same-symbol additions restricted to ultra-high quality
      85 - 100:  EXTREME  -> 0.0x risk sizing, all new risk blocked
    """
    def __init__(
        self,
        max_portfolio_risk_pct: float = 2.5,
        max_daily_loss_pct: float = 4.0,
        max_margin_utilization_pct: float = 40.0,
        max_open_positions: int = 3,
        heat_moderate_thresh: float = 50.0,
        heat_high_thresh: float = 70.0,
        heat_extreme_thresh: float = 85.0,
    ):
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_margin_utilization_pct = max_margin_utilization_pct
        self.max_open_positions = max_open_positions
        self.heat_moderate_thresh = heat_moderate_thresh
        self.heat_high_thresh = heat_high_thresh
        self.heat_extreme_thresh = heat_extreme_thresh

    def calculate_heat(
        self,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        open_monetary_risk_usd: float = 0.0,
        correlation_penalty: float = 0.0
    ) -> PortfolioHeatResult:
        if not account or account.equity <= 0:
            return PortfolioHeatResult(
                score=100.0,
                zone="EXTREME",
                risk_multiplier=0.0,
                allow_new_risk=False,
                allow_same_symbol_addition=False,
                components={"equity": 0.0},
                reasons=["Account equity is zero or unavailable."]
            )

        equity = account.equity
        balance = account.balance

        # 1. Open Risk Component (Weight: 30%)
        # Open risk as % of equity compared to max portfolio risk
        open_risk_pct = (open_monetary_risk_usd / equity) * 100.0 if equity > 0 else 0.0
        c_risk = min(100.0, (open_risk_pct / self.max_portfolio_risk_pct) * 100.0)

        # 2. Drawdown Component (Weight: 25%)
        # Floating or daily drawdown compared to max daily loss limit
        float_dd_usd = max(0.0, balance - equity) if equity < balance else 0.0
        float_dd_pct = (float_dd_usd / balance) * 100.0 if balance > 0 else 0.0
        c_dd = min(100.0, (float_dd_pct / self.max_daily_loss_pct) * 100.0)

        # 3. Margin Utilization Component (Weight: 20%)
        margin_pct = (account.margin / equity) * 100.0 if equity > 0 else 0.0
        c_margin = min(100.0, (margin_pct / self.max_margin_utilization_pct) * 100.0)

        # 4. Position Density Component (Weight: 15%)
        num_pos = len(positions)
        c_pos = min(100.0, (num_pos / self.max_open_positions) * 100.0)

        # 5. Correlation & Volatility Stress Component (Weight: 10%)
        c_corr = min(100.0, max(0.0, correlation_penalty * 100.0))

        # Composite Weighted Heat Score
        raw_heat = (
            0.30 * c_risk +
            0.25 * c_dd +
            0.20 * c_margin +
            0.15 * c_pos +
            0.10 * c_corr
        )
        score = round(min(100.0, max(0.0, raw_heat)), 2)

        # Zone determination
        reasons = []
        if score >= self.heat_extreme_thresh:
            zone = "EXTREME"
            risk_multiplier = 0.0
            allow_new_risk = False
            allow_same_symbol = False
            reasons.append(f"Extreme portfolio heat ({score:.1f}/100 >= {self.heat_extreme_thresh}). New risk blocked.")
        elif score >= self.heat_high_thresh:
            zone = "HIGH"
            risk_multiplier = 0.50
            allow_new_risk = True
            allow_same_symbol = False
            reasons.append(f"High portfolio heat ({score:.1f}/100). Position sizing scaled to 50%; same-symbol additions restricted.")
        elif score >= self.heat_moderate_thresh:
            zone = "MODERATE"
            risk_multiplier = 0.75
            allow_new_risk = True
            allow_same_symbol = True
            reasons.append(f"Moderate portfolio heat ({score:.1f}/100). Position sizing scaled to 75%.")
        else:
            zone = "NORMAL"
            risk_multiplier = 1.0
            allow_new_risk = True
            allow_same_symbol = True

        components = {
            "open_risk_pct": round(open_risk_pct, 2),
            "risk_component": round(c_risk, 1),
            "drawdown_pct": round(float_dd_pct, 2),
            "drawdown_component": round(c_dd, 1),
            "margin_pct": round(margin_pct, 2),
            "margin_component": round(c_margin, 1),
            "position_count": num_pos,
            "position_component": round(c_pos, 1),
            "correlation_component": round(c_corr, 1)
        }

        return PortfolioHeatResult(
            score=score,
            zone=zone,
            risk_multiplier=risk_multiplier,
            allow_new_risk=allow_new_risk,
            allow_same_symbol_addition=allow_same_symbol,
            components=components,
            reasons=reasons
        )
