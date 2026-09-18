from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_connect_args = {"check_same_thread": False} if get_settings().database_url.startswith("sqlite") else {}
engine = create_engine(get_settings().database_url, connect_args=_connect_args)


def init_db() -> None:
    # Import models so their tables are registered on SQLModel.metadata before create_all.
    import app.auth.models  # noqa: F401
    import app.history.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
