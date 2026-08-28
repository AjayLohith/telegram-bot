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


app = FastAPI(title="Personal AI OS", version="0.2.0", lifespan=lifespan)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "online",
        "service": "Personal AI OS - Telegram Productivity & News Intelligence Bot",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str | int | None]:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
        del_repo = DeliveryRepository(session)
        last_7am = del_repo.get_last_successful_7am_delivery()
        
        last_art = session.query(NewsArticle).order_by(NewsArticle.published_at.desc()).first()
        last_fetch = last_art.published_at.isoformat() if last_art else None
        active_reminders = session.query(Reminder).filter_by(active=True).count()

    return {
        "status": "ok",
        "database": "ok",
        "scheduler": "active",
        "target_news_time": "07:00 AM IST",
        "last_successful_news_fetch": last_fetch,
        "last_successful_7am_delivery": last_7am.isoformat() if last_7am else None,
        "active_reminders_count": active_reminders,
    }
