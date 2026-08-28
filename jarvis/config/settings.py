"""JARVIS AI 4.0 Settings Engine."""
import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("JARVIS_Config")

@dataclass
class RiskSettings:
    max_risk_per_trade_pct: float = 0.5
    max_portfolio_risk_pct: float = 2.5
    max_daily_loss_pct: float = 4.0
    max_drawdown_pct: float = 10.0
    max_open_positions: int = 3
    max_symbol_positions: int = 2
    min_rr_ratio: float = 2.0
    min_confidence_floor: float = 0.50
    breakeven_atr_multiple: float = 1.0
    partial_tp_ratio: float = 0.50
    partial_tp_r_multiple: float = 1.5

@dataclass
class TradingSettings:
    default_mode: str = "live"
    magic_number: int = 888999
    primary_timeframe: str = "H1"
    macro_timeframe: str = "D1"
    symbols: List[str] = field(default_factory=lambda: ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"])
    same_symbol_cooldown_sec: int = 600

@dataclass
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8501
    cors_origin: str = "*"
    rate_limit_lockout_sec: float = 60.0
    max_login_attempts: int = 5

@dataclass
class MLSettings:
    sgd_learning_rate: float = 0.05
    sgd_l2_regularization: float = 0.01
    brier_score_drift_threshold: float = 0.28
    meta_labeler_min_window: int = 30
    meta_labeler_min_prob: float = 0.55
    bandit_exploration_c: float = 1.414

@dataclass
class JarvisConfig:
    risk: RiskSettings = field(default_factory=RiskSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    ml: MLSettings = field(default_factory=MLSettings)

    @classmethod
    def load(cls) -> "JarvisConfig":
        cfg = cls()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_path = os.path.join(base_dir, "config", "settings.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                r_data = data.get("risk", {})
                if "max_risk_per_trade_pct" in r_data:
                    cfg.risk.max_risk_per_trade_pct = float(r_data["max_risk_per_trade_pct"])
                if "max_daily_loss_pct" in r_data:
                    cfg.risk.max_daily_loss_pct = float(r_data["max_daily_loss_pct"])
                if "max_open_positions" in r_data:
                    cfg.risk.max_open_positions = int(r_data["max_open_positions"])
                t_data = data.get("trading", {})
                if "allowed_symbols" in t_data:
                    cfg.trading.symbols = list(t_data["allowed_symbols"])
                if "magic_number" in t_data:
                    cfg.trading.magic_number = int(t_data["magic_number"])
            except Exception as e:
                logger.warning(f"Could not load config/settings.json: {e}")

        env_mode = os.environ.get("JARVIS_MODE")
        if env_mode:
            cfg.trading.default_mode = env_mode.lower()
        env_port = os.environ.get("JARVIS_PORT")
        if env_port and env_port.isdigit():
            cfg.server.port = int(env_port)
        env_symbols = os.environ.get("JARVIS_SYMBOLS")
        if env_symbols:
            cfg.trading.symbols = [s.strip().upper() for s in env_symbols.split(",") if s.strip()]
        env_risk = os.environ.get("JARVIS_MAX_RISK_PCT")
        if env_risk:
            try:
                cfg.risk.max_risk_per_trade_pct = float(env_risk)
            except Exception:
                pass
        return cfg

SETTINGS = JarvisConfig.load()
