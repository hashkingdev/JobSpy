from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database() -> None:
    url = make_url(DATABASE_URL)
    db_name = url.database
    if not db_name:
        raise ValueError("DATABASE_URL must include a database name")

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def ensure_columns() -> None:
    """Add columns introduced after the table was first created."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE job_links ADD COLUMN IF NOT EXISTS site VARCHAR(120)"))
