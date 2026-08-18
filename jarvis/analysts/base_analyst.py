"""
JARVIS AI 3.0 — Abstract Base Analyst Agent.
Defines the standard asynchronous and synchronous execution contract for specialized analytical intelligence agents.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole

class BaseAnalyst(ABC):
    def __init__(self, role: AnalystRole):
        self.role = role

    @abstractmethod
    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        """Executes domain analysis and outputs a structured AnalystReport."""
        pass
