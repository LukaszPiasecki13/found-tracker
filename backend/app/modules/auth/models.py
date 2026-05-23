from sqlalchemy import BigInteger, Boolean, Column, DateTime, String

from app.infrastructure.sql.base import Base


class User(Base):
    __tablename__ = "authentication_userprofile"

    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(254), unique=True, nullable=False)
    password_hash = Column("password", String(128), nullable=False)
    status = Column(String(30), nullable=False, default="regular")
    main_currency = Column(String(3), nullable=False, default="PLN")
    is_active = Column(Boolean, nullable=False, default=True)
    # Django-required columns - managed by Django admin, not used by FastAPI
    first_name = Column(String(150), nullable=False, default="")
    last_name = Column(String(150), nullable=False, default="")
    is_superuser = Column(Boolean, nullable=False, default=False)
    is_staff = Column(Boolean, nullable=False, default=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    date_joined = Column(DateTime(timezone=True), nullable=False)
