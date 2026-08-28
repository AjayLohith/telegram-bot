from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/app.db"
    data_dir: Path = Path("./data")
    telegram_bot_token: str | None = None
    telegram_owner_id: int | None = None
    admin_telegram_ids: str = ""  # Comma-separated list of admin telegram user IDs
    log_level: str = "INFO"
    telegram_polling: bool = True
    timezone: str = "Asia/Kolkata"
    
    # Environment
    environment: str = "production"  # "production" or "development"
    
    # News & Reminders Default Times (HH:MM in 24h format)
    news_time: str = "07:00"
    morning_time: str = "08:00"
    video_reminder_time: str = "10:00"
    study_reminder_time: str = "14:00"
    exercise_reminder_time: str = "18:00"
    eod_time: str = "21:00"
    
    # News Retry Settings (at 07:00:00, 07:00:05, 07:00:15, 07:00:30, 07:01:00)
    news_retry_max_attempts: int = 5
    news_retry_backoff_seconds: list[int] = [0, 5, 15, 30, 60]

    
    # Defaults
    streak_threshold: float = 70.0
    breaking_news_enabled: bool = True
    missed_reminders_enabled: bool = True
    morning_combined_enabled: bool = False
    news_language: str = "en"  # "en", "te", "bilingual"
    
    # API Keys
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    mistral_api_key: str | None = None
    mistral_model: str = "mistral-small-latest"
    gemini_api_key: str | None = None
    news_api_key: str | None = None
    turso_auth_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


    @property
    def admin_ids(self) -> set[int]:
        ids = set()
        if self.telegram_owner_id:
            ids.add(self.telegram_owner_id)
        if self.admin_telegram_ids:
            for item in self.admin_telegram_ids.split(","):
                item = item.strip()
                if item.isdigit():
                    ids.add(int(item))
        return ids

    def ensure_data_dirs(self) -> None:
        for path in (self.data_dir, self.data_dir / "memory", self.data_dir / "documents", self.data_dir / "exports"):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()

