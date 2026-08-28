from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FitnessEntry(Base):
    __tablename__ = "fitness_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    walking: Mapped[int] = mapped_column(Integer, default=0)
    pushups: Mapped[int] = mapped_column(Integer, default=0)
    water: Mapped[int] = mapped_column(Integer, default=0)


class FitnessRepository:
    def __init__(self, session):
        self.session = session

    def today(self, user_id: int, day: date) -> FitnessEntry:
        entry = self.session.query(FitnessEntry).filter_by(user_id=user_id, day=day).first()
        if entry is None:
            entry = FitnessEntry(user_id=user_id, day=day)
            self.session.add(entry)
            self.session.commit()
        return entry

    def add(self, user_id: int, day: date, field: str, amount: int) -> FitnessEntry:
        if field not in {"walking", "pushups", "water"} or amount <= 0:
            raise ValueError("field must be walking, pushups, or water and amount must be positive")
        entry = self.today(user_id, day)
        setattr(entry, field, getattr(entry, field) + amount)
        self.session.commit()
        return entry
