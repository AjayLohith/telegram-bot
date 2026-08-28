from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


import os
from pathlib import Path

if settings.database_url.startswith("sqlite"):
    db_path_str = settings.database_url.replace("sqlite:///", "")
    if db_path_str and db_path_str != ":memory:":
        db_path = Path(db_path_str).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
if settings.database_url.startswith("sqlite"):
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    except Exception:
        pass
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)




def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    from app.database.models import DailyNewsDelivery, DailySummary, NewsArticle, NewsDigest, Reminder, Task, TaskCompletion, User
    from app.memory.models import Memory, MemoryDocument, MemoryRevision
    from app.fitness.models import FitnessEntry

    # Check for legacy table structures and migrate if needed
    if settings.database_url.startswith("sqlite"):
        with engine.connect() as conn:
            # Check reminders table columns
            try:
                cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(reminders)").fetchall()]
                if cols and "telegram_user_id" not in cols:
                    conn.exec_driver_sql("DROP TABLE reminders")
                    conn.commit()
            except Exception:
                pass

    Base.metadata.create_all(engine)



