import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Default to a local SQLite file; override with the DATABASE_URL environment variable.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./business.db")

# SQLite requires check_same_thread=False because FastAPI serves requests from a thread pool.
connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

# Engine that owns the connection pool.
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    # Set SQL_ECHO=true to log every SQL statement (useful while debugging).
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

# Session factory used to create a short-lived session per request.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    """Yield a database session and make sure it is closed after the request."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
