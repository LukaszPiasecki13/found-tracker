from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models across the application"""

    # Use configured database schema so the application is flexible.
    metadata = MetaData(schema=get_settings().database_schema)
