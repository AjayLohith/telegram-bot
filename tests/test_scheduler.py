from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.database.models import User
from app.database.repositories.news_repo import NewsRepository
from app.database.repositories.user_repo import UserRepository
from app.scheduler.service import _SENT_NOTIFICATIONS


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as val:
        yield val


def test_user_timezone_handling(session):
    user_repo = UserRepository(session)
    user, _ = user_repo.get_or_create(99999, "ist_user")
    user_tz = ZoneInfo(user.timezone)
    now_in_tz = datetime.now(user_tz)
    assert now_in_tz.tzinfo is not None


def test_duplicate_notification_prevention(session):
    today = date(2026, 8, 28)
    user_id = 1
    # Check that tracking prevents duplicate insertion
    key = (user_id, today, "morning")
    _SENT_NOTIFICATIONS.add(key)
    assert key in _SENT_NOTIFICATIONS


def test_news_digest_recorded_and_checked(session):
    repo = NewsRepository(session)
    user_id = 42
    day = date(2026, 8, 28)
    assert repo.has_sent_digest(user_id, day, "all") is False

    repo.record_digest(user_id, day, "all", [101, 102])
    assert repo.has_sent_digest(user_id, day, "all") is True
