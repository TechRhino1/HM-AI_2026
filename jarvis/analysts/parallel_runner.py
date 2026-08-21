"""
JARVIS AI 3.0 — Parallel Analyst Cluster Orchestrator.
Dispatches all specialized analyst agents concurrently via asyncio / ThreadPool with timeout protection.
"""
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Any

from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, DevilAdvocateReport
from jarvis.analysts.structure_analyst import StructureAnalyst
from jarvis.analysts.momentum_analyst import MomentumAnalyst
from jarvis.analysts.liquidity_analyst import LiquidityAnalyst
from jarvis.analysts.volatility_analyst import VolatilityAnalyst
from jarvis.analysts.macro_analyst import MacroAnalyst
from jarvis.analysts.risk_analyst import RiskAnalyst
from jarvis.analysts.devil_advocate import DevilAdvocateAnalyst
from jarvis.application.timeout_guard import TimeoutGuard

class ParallelAnalystCluster:
    """Runs all 7 specialized analyst agents concurrently or sequentially to minimize latency."""
    def __init__(self, timeout_sec: float = 2.0, parallel: bool = True):
        self.timeout_sec = timeout_sec
        self.parallel = parallel
        self.structure_analyst = StructureAnalyst()
        self.momentum_analyst = MomentumAnalyst()
        self.liquidity_analyst = LiquidityAnalyst()
        self.volatility_analyst = VolatilityAnalyst()
        self.macro_analyst = MacroAnalyst()
        self.risk_analyst = RiskAnalyst()
        self.devil_advocate = DevilAdvocateAnalyst()
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="analyst_worker") if parallel else None

    def run_all_parallel(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        tentative_bias: str = "BUY"
    ) -> Tuple[Dict[str, AnalystReport], DevilAdvocateReport]:
        """
        Executes all analysts concurrently in parallel or sequentially.
        Returns a tuple of (Dict of domain AnalystReports, DevilAdvocateReport).
        """
        if not self.parallel or self._executor is None:
            reports = {
                "STRUCTURE": self.structure_analyst.analyze(context, regime),
                "MOMENTUM": self.momentum_analyst.analyze(context, regime),
                "LIQUIDITY": self.liquidity_analyst.analyze(context, regime),
                "VOLATILITY": self.volatility_analyst.analyze(context, regime),
                "MACRO": self.macro_analyst.analyze(context, regime),
                "RISK": self.risk_analyst.analyze(context, regime),
            }
            devil_report = self.devil_advocate.critique_opportunity(context, regime, tentative_bias)
            return reports, devil_report

        futures = {
            "STRUCTURE": self._executor.submit(self.structure_analyst.analyze, context, regime),
            "MOMENTUM": self._executor.submit(self.momentum_analyst.analyze, context, regime),
            "LIQUIDITY": self._executor.submit(self.liquidity_analyst.analyze, context, regime),
            "VOLATILITY": self._executor.submit(self.volatility_analyst.analyze, context, regime),
            "MACRO": self._executor.submit(self.macro_analyst.analyze, context, regime),
            "RISK": self._executor.submit(self.risk_analyst.analyze, context, regime),
        }

        # Devil's Advocate runs against tentative bias
        devil_future = self._executor.submit(self.devil_advocate.critique_opportunity, context, regime, tentative_bias)

        reports: Dict[str, AnalystReport] = {}
        for role_name, fut in futures.items():
            try:
                reports[role_name] = fut.result(timeout=self.timeout_sec)
            except Exception:
                # Instant zero-overhead fallback report if worker times out or errors
                reports[role_name] = AnalystReport(
                    role=role_name,
                    symbol=context.symbol,
                    bias="NEUTRAL",
                    score=50.0,
                    confidence=0.50,
                    evidence=[f"{role_name} timeout / neutral fallback"],
                    risk_factors=[]
                )

        try:
            devil_report = devil_future.result(timeout=self.timeout_sec)
        except Exception:
            devil_report = DevilAdvocateReport(
                symbol=context.symbol,
                counter_bias="NEUTRAL",
                penalty_score=0.0,
                invalidation_risk_coefficient=0.0,
                threats_detected=[],
                invalidation_triggers=[],
                liquidity_traps=[]
            )

        return reports, devil_report
