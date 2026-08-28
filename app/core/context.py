from dataclasses import dataclass, field

from app.memory.models import Memory
from app.memory.repository import MemoryRepository


@dataclass(frozen=True)
class ContextPackage:
    user_profile: dict[str, str] = field(default_factory=dict)
    preferences: dict[str, str] = field(default_factory=dict)
    relevant_memories: list[dict[str, str]] = field(default_factory=list)
    relevant_skills: list[str] = field(default_factory=list)
    recent_context: list[str] = field(default_factory=list)
    relevant_articles: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


class ContextEngine:
    def __init__(self, memories: MemoryRepository):
        self.memories = memories

    def build(self, user_id: int, task: str, current_message: str, conversation_id: str | None = None) -> ContextPackage:
        query = f"{task} {current_message}"
        candidates = self.memories.search(user_id, query) if query.strip() else self.memories.list(user_id)
        selected = self._select_authoritative(candidates)
        preferences = {memory.key: memory.value for memory in selected if memory.category in {"preference", "preferences", "response_style", "news_preferences"}}
        profile = {memory.key: memory.value for memory in selected if memory.category in {"profile", "user_profile"}}
        constraints = [memory.value for memory in selected if memory.category in {"preference", "preferences", "news_preferences"}]
        return ContextPackage(
            user_profile=profile,
            preferences=preferences,
            relevant_memories=[{"key": m.key, "value": m.value, "source": m.source} for m in selected],
            constraints=constraints,
        )

    @staticmethod
    def _select_authoritative(memories: list[Memory]) -> list[Memory]:
        rank = {"explicit": 4, "high": 3, "medium": 2, "low": 1}
        chosen: dict[str, Memory] = {}
        for memory in sorted(memories, key=lambda item: (rank.get(item.confidence, 0), item.updated_at), reverse=True):
            if memory.key not in chosen:
                chosen[memory.key] = memory
        return list(chosen.values())
