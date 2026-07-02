"""Privacy-first analytics sink.

Track product events (sessions, deal outcomes, purchase funnel, concept mastery)
— never PII. The interface + a NoOp and an in-memory sink live here so the rest
of the app can emit events with zero device dependency; the on-device sink
(batched HTTPS to your analytics endpoint) is wired in Phase 6.

Design rule: callers pass an event name + a small dict of *non-identifying*
properties. There is deliberately no field for user identity here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    name: str
    props: dict[str, Any] = field(default_factory=dict)


class AnalyticsSink(ABC):
    @abstractmethod
    def emit(self, event: Event) -> None: ...


class NoOpAnalytics(AnalyticsSink):
    """Default — drops everything (used until the player opts in)."""

    def emit(self, event: Event) -> None:
        return None


class InMemoryAnalytics(AnalyticsSink):
    """For tests/dev: keep events so funnels can be asserted."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def count(self, name: str) -> int:
        return sum(1 for e in self.events if e.name == name)
