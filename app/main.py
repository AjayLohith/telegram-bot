import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import SessionLocal, init_db
from app.database.models import NewsArticle, Reminder
from app.database.repositories.delivery_repo import DeliveryRepository
from app.telegram_bot import start_polling_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Purge legacy cached news containing old URLs on startup (Master Prompt V2 Section 3)
    with SessionLocal() as session:
        del_repo = DeliveryRepository(session)
        del_repo.purge_bad_news_cache()

    telegram_task = start_polling_task()
    try:
        yield
    finally:
        if telegram_task is not None:
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="J.A.R.V.I.S. // Personal AI OS", version="0.2.0", lifespan=lifespan)


@app.api_route("/", methods=["GET", "HEAD"])
def root() -> dict[str, str]:
    return {
        "status": "online",
        "system": "J.A.R.V.I.S. Mark VII - Telegram Productivity & News Intelligence Assistant",
        "health": "/health",
        "ping": "/ping",
        "docs": "/docs",
    }


@app.api_route("/ping", methods=["GET", "HEAD"])
def ping() -> dict[str, str]:
    return {"status": "ok", "message": "pong"}


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str | int | None]:
    db_status = "ok"
    last_fetch = None
    last_7am = None
    active_reminders = 0

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            del_repo = DeliveryRepository(session)
            last_7am_val = del_repo.get_last_successful_7am_delivery()
            if last_7am_val:
                last_7am = last_7am_val.isoformat()

            last_art = session.query(NewsArticle).order_by(NewsArticle.published_at.desc()).first()
            if last_art and last_art.published_at:
                last_fetch = last_art.published_at.isoformat()
            active_reminders = session.query(Reminder).filter_by(active=True).count()
    except Exception as e:
        db_status = f"degraded: {e}"

    return {
        "status": "ok",
        "database": db_status,
        "scheduler": "active",
        "target_news_time": "07:00 AM IST",
        "last_successful_news_fetch": last_fetch,
        "last_successful_7am_delivery": last_7am,
        "active_reminders_count": active_reminders,
    }
