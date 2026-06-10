"""Unit tests for app/db/migrate.py — discovery, ordering, and pending selection."""

from pathlib import Path

from app.db.migrate import _asyncpg_dsn, discover_migrations, migrations_dir, pending_migrations


def _touch(directory: Path, name: str) -> Path:
    f = directory / name
    f.write_text("SELECT 1;")
    return f


def test_discover_migrations_sorted_by_filename(tmp_path: Path):
    _touch(tmp_path, "20260609000002_billing.sql")
    _touch(tmp_path, "20260608120001_extensions.sql")
    _touch(tmp_path, "20260608130002_users.sql")
    (tmp_path / "README.md").write_text("not a migration")

    files = discover_migrations(tmp_path)

    assert [f.name for f in files] == [
        "20260608120001_extensions.sql",
        "20260608130002_users.sql",
        "20260609000002_billing.sql",
    ]


def test_pending_skips_applied_versions(tmp_path: Path):
    _touch(tmp_path, "001_a.sql")
    _touch(tmp_path, "002_b.sql")
    _touch(tmp_path, "003_c.sql")
    files = discover_migrations(tmp_path)

    pending = pending_migrations(files, applied_versions={"001_a", "002_b"})

    assert [f.name for f in pending] == ["003_c.sql"]


def test_pending_empty_when_all_applied(tmp_path: Path):
    _touch(tmp_path, "001_a.sql")
    files = discover_migrations(tmp_path)
    assert pending_migrations(files, applied_versions={"001_a"}) == []


def test_migrations_dir_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MIGRATIONS_DIR", str(tmp_path))
    assert migrations_dir() == tmp_path


def test_migrations_dir_repo_fallback(monkeypatch):
    monkeypatch.delenv("MIGRATIONS_DIR", raising=False)
    resolved = migrations_dir()
    # Local checkout: resolves to <repo>/supabase/migrations with real files.
    assert resolved.name == "migrations"
    assert any(resolved.glob("*.sql"))


def test_asyncpg_dsn_strips_driver_suffix():
    assert (
        _asyncpg_dsn("postgresql+asyncpg://u:p@host:5432/db")
        == "postgresql://u:p@host:5432/db"
    )


def test_asyncpg_dsn_passthrough_plain():
    assert _asyncpg_dsn("postgresql://u:p@host/db") == "postgresql://u:p@host/db"
