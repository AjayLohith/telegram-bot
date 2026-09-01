import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.providers import AIRouter, CallableProvider
from app.core.context import ContextEngine
from app.core.database import Base
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.news.normalization import canonical_url
from app.news.digest import _clean, _is_fresh, _reasons, split_digest_sections
from app.reminders.service import parse_relative_reminder


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as value:
        yield value


def test_memory_import_export_and_explicit_precedence(session):
    service = MemoryService(MemoryRepository(session))
    service.import_markdown(7, "preferences.md", "# Preferences\n\n## News Preferences\n- topic: technical AI")
    service.remember(7, "topic", "general world news", category="news_preferences")
    exported = service.export_markdown(7)
    assert "general world news" in exported
    context = ContextEngine(MemoryRepository(session)).build(7, "news", "today's news")
    assert context.preferences["topic"] == "general world news"


@pytest.mark.asyncio
async def test_router_fails_over_and_cools_down():
    calls = []

    async def broken(prompt):
        calls.append("broken")
        raise TimeoutError("down")

    async def working(prompt):
        calls.append("working")
        return "ok"

    router = AIRouter({"one": CallableProvider("one", broken), "two": CallableProvider("two", working)}, {"reasoning": ["one", "two"]})
    assert await router.complete("reasoning", "hello") == "ok"
    assert calls == ["broken", "working"]
    assert await router.complete("reasoning", "again") == "ok"
    assert calls == ["broken", "working", "working"]


def test_reminder_parser_and_article_url_normalization():
    from datetime import datetime, timezone

    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    reminder = parse_relative_reminder("/remind me in 2 hours to check the build", now)
    assert reminder is not None
    assert reminder.text == "check the build"
    assert reminder.trigger_at == datetime(2026, 8, 24, 14, tzinfo=timezone.utc)
    assert canonical_url("HTTPS://Example.com/story/?utm_source=x") == "https://example.com/story"


def test_digest_format_has_category_reasons_and_fresh_timestamp_support():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    assert _is_fresh(datetime.now(), cutoff)
    hot_reason, read_reason = _reasons("AI")
    assert "infrastructure" in hot_reason
    assert "developers" in read_reason


def test_digest_sections_are_separate_messages():
    digest = "<b>DAILY</b>\n<b>AI | 5 STORIES</b>\nAI text\n<b>WORLD AND INDIA | 5 STORIES</b>\nWorld text"
    sections = split_digest_sections(digest)
    assert len(sections) == 3
    assert sections[0].startswith("<b>DAILY</b>")
    assert sections[1].startswith("<b>AI | 5 STORIES</b>")
    assert sections[2].startswith("<b>WORLD AND INDIA | 5 STORIES</b>")


def test_digest_removes_escaped_rss_links_and_indents_bullets():
    assert "href" not in _clean("&lt;a href=\"https://example.com\"&gt;RSS link&lt;/a&gt;")
    assert "https://" not in _clean("Read https://example.com for details")


def test_health_and_ping_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"

    ping_resp = client.get("/ping")
    assert ping_resp.status_code == 200
    assert ping_resp.json()["status"] == "ok"

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

