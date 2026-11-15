from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Database URL comes from Settings, so it can be set through .env or environment variables.
# Examples: sqlite:///./business.db, postgresql+psycopg://user:pass@127.0.0.1:5432/dbname
DATABASE_URL = settings.database_url

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
    # Set SQL_ECHO=true in .env to log every SQL statement (useful while debugging).
    echo=settings.sql_echo,
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
