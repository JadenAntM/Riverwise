from app.config import Settings, normalize_database_url


def test_normalize_database_url_selects_psycopg_for_postgresql() -> None:
    assert (
        normalize_database_url("postgresql://riverwise:secret@db.internal:5432/riverwise")
        == "postgresql+psycopg://riverwise:secret@db.internal:5432/riverwise"
    )


def test_normalize_database_url_accepts_legacy_postgres_scheme() -> None:
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_normalize_database_url_preserves_explicit_driver_and_sqlite() -> None:
    psycopg_url = "postgresql+psycopg://user:pass@host/db"
    sqlite_url = "sqlite:///riverwise.sqlite3"

    assert normalize_database_url(psycopg_url) == psycopg_url
    assert normalize_database_url(sqlite_url) == sqlite_url


def test_settings_normalize_provider_database_url() -> None:
    settings = Settings(database_url="postgresql://user:pass@host/db")

    assert settings.database_url == "postgresql+psycopg://user:pass@host/db"
