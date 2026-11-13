from backend.database.base import Base
from backend.database.models import (  # noqa: F401 - register models with metadata
    ConversationHistory,
    Delivery,
    Product,
    Supplier,
    User,
)
from backend.database.session import engine


def init_db() -> None:
    """Create missing tables for local development and initial prototyping."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables are ready.")
