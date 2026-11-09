import os
from collections.abc import Iterator
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlmodel import Field, Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./contacts.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


class ContactBase(SQLModel):
    nome: str = Field(min_length=1, max_length=100)
    cognome: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=255)
    messaggio: str = Field(min_length=1, max_length=5000)


class Contact(ContactBase, table=True):
    __tablename__ = "contacts"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContactCreate(ContactBase):
    pass


class ContactRead(ContactBase):
    id: int
    created_at: datetime


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


class UsedCaptcha(SQLModel, table=True):
    __tablename__ = "used_captchas"

    signature: str = Field(primary_key=True, max_length=64)
    expires_at: datetime = Field(index=True)
