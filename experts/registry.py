"""Expert registry for assistant orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from experts.base import ExpertPlugin


@dataclass
class ExpertRegistry:
    _by_name: dict[str, ExpertPlugin] = field(default_factory=dict)
    _by_intent: dict[str, str] = field(default_factory=dict)

    def register(self, expert: ExpertPlugin) -> None:
        self._by_name[expert.name] = expert
        for intent in expert.intents:
            self._by_intent[intent] = expert.name

    def get_by_name(self, name: str) -> ExpertPlugin:
        if name not in self._by_name:
            raise KeyError(f"Unknown expert: {name}")
        return self._by_name[name]

    def resolve_intent(self, intent: str) -> ExpertPlugin:
        name = self._by_intent.get(intent)
        if not name:
            raise KeyError(f"No expert registered for intent: {intent}")
        return self.get_by_name(name)

    def list_experts(self) -> list[str]:
        return sorted(self._by_name.keys())
