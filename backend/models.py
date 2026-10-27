from sqlalchemy import Column, Date, DateTime, Integer, String, Text, func

from backend.db import Base


class JobLink(Base):
    __tablename__ = "job_links"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=False, default="")
    role = Column(String(255), nullable=False, default="")
    url = Column(Text, nullable=False)
    location = Column(String(255), nullable=False, default="")
    site = Column(String(120), nullable=True)
    job_description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DailyRun(Base):
    __tablename__ = "daily_runs"

    id = Column(Integer, primary_key=True)
    run_date = Column(Date, nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")
    trigger = Column(String(20), nullable=False, default="schedule")
    target = Column(Integer, nullable=False)
    saved = Column(Integer, nullable=False, default=0)
    found = Column(Integer, nullable=False, default=0)
    filtered = Column(Integer, nullable=False, default=0)
    duplicates = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
