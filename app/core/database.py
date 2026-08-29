from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


import os
from pathlib import Path

db_url = settings.database_url
if db_url.startswith("libsql://"):
    host = db_url.replace("libsql://", "").split("?")[0]
    token = getattr(settings, "turso_auth_token", None)
    if token and "authToken=" not in db_url:
        db_url = f"sqlite+libsql://{host}?authToken={token}&secure=true"
    else:
        db_url = db_url.replace("libsql://", "sqlite+libsql://", 1)


if db_url.startswith("sqlite://"):
    db_path_str = db_url.replace("sqlite:///", "")
    if db_path_str and db_path_str != ":memory:" and not db_path_str.startswith("http"):
        db_path = Path(db_path_str).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False, "timeout": 30} if "sqlite" in db_url and "libsql" not in db_url else {}
try:
    engine = create_engine(db_url, connect_args=connect_args)
    with engine.connect() as conn:
        pass
except Exception as e:
    # If remote dialect fails, fallback gracefully to local SQLite
    local_db_path = Path("./data/app.db").resolve()
    local_db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{local_db_path}", connect_args={"check_same_thread": False, "timeout": 30})

if str(engine.url).startswith("sqlite://") and "libsql" not in str(engine.url):
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



