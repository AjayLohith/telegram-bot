from __future__ import annotations

from hashlib import sha256

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.memory.models import Memory, MemoryDocument, MemoryRevision, utc_now


class MemoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self, user_id: int) -> list[Memory]:
        return list(self.session.scalars(select(Memory).where(Memory.user_id == user_id).order_by(Memory.category, Memory.key)))

    def search(self, user_id: int, query: str) -> list[Memory]:
        terms = [term for term in query.lower().split() if len(term) > 2]
        if not terms:
            return self.list(user_id)
        matches = [
            Memory.key.ilike(f"%{term}%")
            | Memory.value.ilike(f"%{term}%")
            | Memory.category.ilike(f"%{term}%")
            for term in terms
        ]
        statement = select(Memory).where(Memory.user_id == user_id).where(or_(*matches))
        return list(self.session.scalars(statement))

    def upsert(self, user_id: int, key: str, value: str, *, category: str = "general", source: str = "user", confidence: str = "medium") -> Memory:
        memory = self.session.scalar(select(Memory).where(Memory.user_id == user_id, Memory.key == key))
        if memory is None:
            memory = Memory(user_id=user_id, key=key)
            self.session.add(memory)
        memory.value = value
        memory.category = category
        memory.source = source
        memory.confidence = confidence
        memory.updated_at = utc_now()
        self.session.commit()
        return memory

    def import_document(self, user_id: int, name: str, content: str) -> MemoryDocument:
        digest = sha256(content.encode("utf-8")).hexdigest()
        current = self.session.scalar(select(MemoryDocument).where(MemoryDocument.user_id == user_id, MemoryDocument.name == name, MemoryDocument.active.is_(True)))
        if current is None:
            current = MemoryDocument(user_id=user_id, name=name, content_hash=digest, content=content)
            self.session.add(current)
            self.session.commit()
            return current
        if current.content_hash == digest:
            return current
        current.active = False
        replacement = MemoryDocument(user_id=user_id, name=name, content_hash=digest, version=current.version + 1, content=content)
        self.session.add(replacement)
        self.session.add(MemoryRevision(document_id=current.id, version=current.version, content=current.content))
        self.session.commit()
        return replacement
