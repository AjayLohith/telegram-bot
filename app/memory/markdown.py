from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownSection:
    title: str
    level: int
    content: str
    parent: str | None = None


def parse_markdown(text: str) -> list[MarkdownSection]:
    sections: list[MarkdownSection] = []
    current_title = "Document"
    current_level = 0
    current_lines: list[str] = []
    parents: dict[int, str] = {}

    def flush() -> None:
        if current_lines or current_title != "Document":
            sections.append(MarkdownSection(current_title, current_level, "\n".join(current_lines).strip(), parents.get(current_level - 1)))

    for line in text.splitlines():
        if line.startswith("#"):
            marker, _, title = line.partition(" ")
            if title and set(marker) == {"#"}:
                flush()
                current_level = len(marker)
                current_title = title.strip()
                current_lines = []
                parents[current_level] = current_title
                continue
        current_lines.append(line)
    flush()
    return [section for section in sections if section.content]
