from dataclasses import dataclass

from app.memory.markdown import MarkdownSection, parse_markdown
from app.memory.repository import MemoryRepository


@dataclass(frozen=True)
class MemoryCandidate:
    key: str
    value: str
    category: str


class MemoryService:
    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    def remember(self, user_id: int, key: str, value: str, *, category: str = "general"):
        return self.repository.upsert(user_id, key, value, category=category, source="explicit", confidence="explicit")

    def import_markdown(self, user_id: int, name: str, content: str):
        document = self.repository.import_document(user_id, name, content)
        for section in parse_markdown(content):
            for candidate in self._candidates(section):
                self.repository.upsert(user_id, candidate.key, candidate.value, category=candidate.category, source=f"document:{name}", confidence="high")
        return document

    def export_markdown(self, user_id: int) -> str:
        grouped: dict[str, list[str]] = {}
        for memory in self.repository.list(user_id):
            grouped.setdefault(memory.category.title(), []).append(f"- **{memory.key}**: {memory.value}")
        return "\n\n".join(f"## {category}\n\n" + "\n".join(values) for category, values in grouped.items())

    @staticmethod
    def _candidates(section: MarkdownSection) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        for line in section.content.splitlines():
            stripped = line.strip().lstrip("-*").strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                if key.strip() and value.strip():
                    candidates.append(MemoryCandidate(key.strip().lower().replace(" ", "_"), value.strip(), section.title.lower().replace(" ", "_")))
        return candidates
