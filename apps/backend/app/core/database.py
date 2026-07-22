from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# pool_pre_ping issues a cheap SELECT 1 before handing out a pooled
# connection, so a connection the server closed while we were idle is
# discarded and replaced instead of blowing up the request. Without it the
# first request after a quiet period fails with "server closed the connection
# unexpectedly" -- and because CORSMiddleware sits inside Starlette's
# ServerErrorMiddleware, that 500 comes back with no Access-Control-Allow-Origin
# header, so the browser reports it as a CORS error rather than a 500.
# pool_recycle caps connection age below the typical idle timeout so most
# staleness is avoided before pre_ping ever has to catch it.
engine = create_engine(
    settings.APP_DATABASE_DSN,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
