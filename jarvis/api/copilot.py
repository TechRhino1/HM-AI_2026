"""
JARVIS AI 3.0 — Conversational AI Copilot Layer.
Answers discretionary trader queries using verified in-memory system state, market context, and decision records.
"""
from typing import Dict, Any, List, Optional
from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.intelligence.reasoning_engine import ReasoningEngine

class JarvisCopilot:
    def __init__(self, state_manager: StateManager = GLOBAL_STATE):
        self.state_manager = state_manager

    def ask(self, query: str) -> str:
        q = query.lower().strip()
        state = self.state_manager.get_state_snapshot()
        latest_decisions = self.state_manager.latest_decisions
        contexts = self.state_manager.market_contexts
        account = self.state_manager.account
        positions = self.state_manager.positions

        # 1. "why aren't you entering" / "why no trade"
        if "why" in q and ("enter" in q or "trade" in q or "reject" in q or "buy" in q or "sell" in q):
            # Check target symbol
            sym = self._find_symbol_in_query(q) or "XAUUSD"
            if sym in latest_decisions:
                d = latest_decisions[sym]
                if d.decision != "EXECUTE":
                    reasons = d.quality_gate.failing_reasons
                    adv_threats = d.risk_factors
                    return (
                        f"**JARVIS 3.0 Decision Status for {sym}: {d.decision}**\n\n"
                        f"- **Current Bias**: {d.bias} ({d.strategy})\n"
                        f"- **Calibrated Win Probability**: {d.probabilities.get(d.bias.lower(), 0.5)*100:.1f}%\n"
                        f"- **Quality Gate Failing Checks**: {', '.join(reasons) if reasons else 'Waiting on Lower Timeframe Trigger'}\n"
                        f"- **Devil's Advocate Adversarial Objections** (Penalty: -{d.adversarial_penalty:.1f} pts):\n"
                        + "\n".join([f"  • {t}" for t in adv_threats[:3]]) + "\n\n"
                        f"- **Invalidation Trigger**: {', '.join(d.invalidation_levels[:2])}"
                    )
                else:
                    return f"**JARVIS 3.0 has APPROVED execution for {sym}**: Bias={d.bias}, EV=${d.expected_value:.2f}, R:R=1:{d.risk_reward_ratio:.2f}."
            return f"No active decision recorded yet for {sym}. Radar is currently scanning market conditions."

        # 2. "analyze [symbol]" / "market status"
        elif "analyze" in q or "status" in q or "context" in q:
            sym = self._find_symbol_in_query(q) or "XAUUSD"
            if sym in latest_decisions:
                return ReasoningEngine.generate_explanation(latest_decisions[sym])
            elif sym in contexts:
                ctx = contexts[sym]
                return (
                    f"**Market Context for {sym}**\n"
                    f"- Price: {ctx.current_price:.2f} (Spread: {ctx.volatility.current_spread_pips} pips)\n"
                    f"- Structure: {ctx.structure.bias} (Zone: {ctx.structure.discount_premium_zone})\n"
                    f"- Momentum Score: {ctx.momentum.trend_score} (ADX: {ctx.momentum.adx:.1f}, RSI: {ctx.momentum.rsi:.1f})\n"
                    f"- Volatility: {ctx.volatility.state} (ATR: {ctx.volatility.atr:.4f})\n"
                    f"- Session: {ctx.session.current_session}"
                )
            return f"Symbol {sym} is currently queued for multi-timeframe synthesis."

        # 3. "risk" / "exposure" / "drawdown"
        elif "risk" in q or "exposure" in q or "drawdown" in q or "account" in q:
            if account:
                return (
                    f"**JARVIS 3.0 Risk & Account Telemetry**\n"
                    f"- Server: {account.server} (#{account.login})\n"
                    f"- Balance: ${account.balance:,.2f} | Equity: ${account.equity:,.2f}\n"
                    f"- Free Margin: ${account.free_margin:,.2f} | Open Margin: ${account.margin:,.2f}\n"
                    f"- Active Positions: {len(positions)} open trades\n"
                    f"- Execution Mode: **{self.state_manager.execution_mode.value}**\n"
                    f"- Safe Mode Lock: {'🟡 ACTIVE (Trading Paused)' if self.state_manager.is_safe_mode else '🟢 OFF'}"
                )
            return "Account data is currently synchronizing with MT5 gateway."

        # 4. "best setups" / "radar" / "opportunities"
        elif "setup" in q or "radar" in q or "best" in q or "scan" in q:
            opps = self.state_manager.radar_opportunities
            if opps:
                lines = ["**Today's Multi-Symbol Scanner Opportunities:**\n"]
                for o in opps[:5]:
                    lines.append(
                        f"- **{o.get('symbol')}**: {o.get('action')} | Score: {o.get('score')}/100 | EV: ${o.get('ev', 0.0):.2f} | Regime: {o.get('regime')} | Status: {o.get('decision')}"
                    )
                return "\n".join(lines)
            return "Scanner is currently performing multi-asset radar sweep."

        # 5. Default conversational intelligence response
        return (
            "**JARVIS 3.0 AI Intelligence Copilot**\n"
            "I have access to live MT5 state, multi-timeframe market context, and adversarial decision telemetry.\n\n"
            "You can ask me:\n"
            "- *'Why aren't you entering XAUUSD?'*\n"
            "- *'Analyze EURUSD'* \n"
            "- *'Show today's best setups'* \n"
            "- *'Show current risk and exposure'* \n"
            "- *'What invalidates the current Gold setup?'*"
        )

    def _find_symbol_in_query(self, query: str) -> Optional[str]:
        for sym in ["XAUUSD", "GOLD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US30", "NAS100"]:
            if sym.lower() in query:
                return "XAUUSD" if sym in ["GOLD", "XAUUSD"] else sym
        return None
