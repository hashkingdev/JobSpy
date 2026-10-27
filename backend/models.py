from sqlalchemy import Column, DateTime, Integer, String, Text, func

from backend.db import Base


class JobLink(Base):
    __tablename__ = "job_links"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)
    url = Column(Text, nullable=False)
    location = Column(String(255), nullable=True)
    job_description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=True)
