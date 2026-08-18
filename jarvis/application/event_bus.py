"""
JARVIS AI 3.0 — Asynchronous Event Bus.
Decouples communication between market data feeds, analyst agents, decision pipelines, and UI streams.
"""
import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("JARVIS_EventBus")

class EventBus:
    """Thread-safe and Async-friendly Publish/Subscribe Event Bus."""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], Any]]] = {}
        self._async_subscribers: Dict[str, List[Callable[[Any], Any]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], Any]) -> None:
        """Subscribe a synchronous callback to an event channel."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_async(self, event_type: str, async_callback: Callable[[Any], Any]) -> None:
        """Subscribe an asynchronous callback to an event channel."""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(async_callback)

    def publish_sync(self, event_type: str, payload: Any) -> None:
        """Synchronously publish an event to all registered sync callbacks."""
        if event_type in self._subscribers:
            for cb in self._subscribers[event_type]:
                try:
                    cb(payload)
                except Exception as e:
                    logger.error(f"EventBus sync callback error on '{event_type}': {e}", exc_info=True)

    async def publish(self, event_type: str, payload: Any) -> None:
        """Asynchronously broadcast an event to both async and sync subscribers."""
        self.publish_sync(event_type, payload)

        if event_type in self._async_subscribers:
            tasks = []
            for async_cb in self._async_subscribers[event_type]:
                try:
                    tasks.append(asyncio.create_task(async_cb(payload)))
                except Exception as e:
                    logger.error(f"EventBus async task creation error on '{event_type}': {e}", exc_info=True)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

# Global singleton event bus
GLOBAL_EVENT_BUS = EventBus()
