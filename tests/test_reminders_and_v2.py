import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.database.repositories.delivery_repo import DeliveryRepository
from app.database.repositories.reminder_repo import ReminderRepository
from app.productivity.reminder_ai import format_reminder_message, generate_reminder_focus
from app.productivity.time_parser import parse_remainder_command, parse_time_string


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_parse_time_string():
    # 24-hour format
    assert parse_time_string("16:04") == ("16:04", "16:04")
    assert parse_time_string("07:00") == ("07:00", "07:00")
    assert parse_time_string("19:30") == ("19:30", "19:30")
    assert parse_time_string("00:00") == ("00:00", "00:00")

    # 12-hour AM/PM
    assert parse_time_string("7:00 AM") == ("07:00", "07:00")
    assert parse_time_string("8:30 PM") == ("20:30", "20:30")

    # Invalid
    assert parse_time_string("invalid") is None
    assert parse_time_string("25:00") is None
    assert parse_time_string("8:60 PM") is None


def test_parse_remainder_command():
    # Direct 24-hour input without slash
    res0 = parse_remainder_command("Study DSA 16:04")
    assert res0 == ("Study DSA", "16:04", "16:04")

    res1 = parse_remainder_command("/remainder Study DSA 8:30 PM")
    assert res1 == ("Study DSA", "20:30", "20:30")

    res2 = parse_remainder_command("Go for exercise 18:00")
    assert res2 == ("Go for exercise", "18:00", "18:00")

    res3 = parse_remainder_command("remind Watch AI lecture 10:30")
    assert res3 == ("Watch AI lecture", "10:30", "10:30")

    # Non-breaking spaces (e.g. mobile copy-paste \xa0 / \u00a0)
    res_nbsp = parse_remainder_command("/remainder\xa0Study DSA 16:04")
    assert res_nbsp == ("Study DSA", "16:04", "16:04")

    # Missing time
    assert parse_remainder_command("/remainder Study") is None
    assert parse_remainder_command("/remainder") is None




def test_reminder_repository_crud(db_session):
    repo = ReminderRepository(db_session)
    rem = repo.add_reminder(
        telegram_user_id=12345,
        task_name="Study DSA",
        reminder_time_24h="20:30",
        display_time_12h="8:30 PM",
        timezone="Asia/Kolkata",
    )
    assert rem.id is not None
    assert rem.task_name == "Study DSA"
    assert rem.reminder_time == "20:30"
    assert rem.display_time == "8:30 PM"
    assert rem.active is True

    # List active
    active = repo.list_active_reminders(12345)
    assert len(active) == 1
    assert active[0].task_name == "Study DSA"

    # Pause reminder
    paused = repo.set_active_status(rem.id, 12345, active=False)
    assert paused.active is False
    assert len(repo.list_active_reminders(12345)) == 0

    # Resume reminder
    resumed = repo.set_active_status(rem.id, 12345, active=True)
    assert resumed.active is True
    assert len(repo.list_active_reminders(12345)) == 1

    # Update reminder
    updated = repo.update_reminder(rem.id, 12345, task_name="Study Algorithms", reminder_time="21:00", display_time="9:00 PM")
    assert updated.task_name == "Study Algorithms"
    assert updated.reminder_time == "21:00"

    # Delete reminder
    deleted = repo.delete_reminder(rem.id, 12345)
    assert deleted is True
    assert repo.get_reminder(rem.id) is None


def test_delivery_repository_state_and_deduplication(db_session):
    repo = DeliveryRepository(db_session)
    today = date(2026, 8, 28)

    # Initial state
    assert repo.is_already_sent(12345, today) is False

    delivery, created = repo.get_or_create_delivery(12345, today, scheduled_time="07:00")
    assert created is True
    assert delivery.status == "SCHEDULED"

    # Updating status
    repo.update_status(delivery.id, "FETCHING")
    repo.update_status(delivery.id, "SENT")
    assert repo.is_already_sent(12345, today) is True

    # Duplicate call returns existing delivery
    delivery2, created2 = repo.get_or_create_delivery(12345, today, scheduled_time="07:00")
    assert created2 is False
    assert delivery2.id == delivery.id


@pytest.mark.asyncio
async def test_reminder_ai_focus_and_formatter():
    bullets = await generate_reminder_focus("Study DSA")
    assert len(bullets) >= 2
    for b in bullets:
        assert len(b) > 5

    msg = format_reminder_message(
        task_name="Study DSA",
        display_time="8:30 PM",
        tz_name="IST",
        focus_bullets=bullets,
    )
    assert "DIRECTIVE REMINDER // J.A.R.V.I.S." in msg
    assert "Study DSA" in msg
    assert "Tactical Focus:" in msg
    assert "8:30 PM IST" in msg
    assert "At your service, sir." in msg


