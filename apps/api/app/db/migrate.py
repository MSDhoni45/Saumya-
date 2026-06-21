"""SQL migration runner — applies pending supabase/migrations/*.sql at container startup.

Invoked by docker-entrypoint.sh (when RUN_MIGRATIONS=1) before the API
process starts, or manually:

    python -m app.db.migrate

Design:
  - A Postgres advisory lock serializes concurrent runners, so an ECS rolling
    deploy starting several containers at once applies each migration exactly
    once (the losers wait, then see everything already applied).
  - Applied versions are tracked in `app_schema_migrations`. Versions already
    recorded by the Supabase CLI (`supabase_migrations.schema_migrations`,
    written by `supabase db push`) are also treated as applied, so adopting
    this runner on an existing database doesn't re-run history.
  - Each migration file runs inside its own transaction: a failure rolls back
    that file completely, leaves earlier migrations applied, and exits non-zero
    so the container never starts on a half-migrated schema.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# Arbitrary but fixed application-wide lock id for "schema migration in progress".
_ADVISORY_LOCK_ID = 87_412_001

_DEFAULT_MIGRATIONS_DIR = "/app/supabase/migrations"


def migrations_dir() -> Path:
    """Resolve the migrations directory (env override → image path → repo checkout)."""
    if env_dir := os.environ.get("MIGRATIONS_DIR"):
        return Path(env_dir)
    image_path = Path(_DEFAULT_MIGRATIONS_DIR)
    if image_path.is_dir():
        return image_path
    # Local dev: apps/api/app/db/migrate.py → repo root / supabase/migrations
    return Path(__file__).resolve().parents[4] / "supabase" / "migrations"


def discover_migrations(directory: Path) -> list[Path]:
    """All migration files in apply order (filename-sorted, matching `supabase db push`)."""
    return sorted(p for p in directory.glob("*.sql") if p.is_file())


def pending_migrations(files: list[Path], applied_versions: set[str]) -> list[Path]:
    """Files whose version (filename stem) has not been applied yet, in order."""
    return [f for f in files if f.stem not in applied_versions]


def _asyncpg_dsn(database_url: str) -> str:
    # settings.database_url is SQLAlchemy-flavored (postgresql+asyncpg://...);
    # asyncpg wants a plain postgresql:// DSN.
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _fetch_applied_versions(conn: asyncpg.Connection) -> set[str]:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_schema_migrations (
            version    text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    rows = await conn.fetch("SELECT version FROM app_schema_migrations")
    applied = {r["version"] for r in rows}

    # Honor migrations the Supabase CLI already pushed to this database.
    cli_table = await conn.fetchval(
        "SELECT to_regclass('supabase_migrations.schema_migrations')"
    )
    if cli_table is not None:
        rows = await conn.fetch("SELECT version FROM supabase_migrations.schema_migrations")
        # CLI stores the leading timestamp as the version; our stems are
        # `<timestamp>_<name>`, so match on the timestamp prefix.
        cli_versions = {r["version"] for r in rows}
        for f in discover_migrations(migrations_dir()):
            if f.stem.split("_", 1)[0] in cli_versions:
                applied.add(f.stem)
    return applied


async def run_migrations() -> int:
    """Apply all pending migrations. Returns the number applied."""
    directory = migrations_dir()
    files = discover_migrations(directory)
    if not files:
        logger.warning("No migration files found in %s — nothing to do", directory)
        return 0

    ssl = True if settings.environment != "local" else None
    conn = await asyncpg.connect(_asyncpg_dsn(settings.database_url), ssl=ssl)
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", _ADVISORY_LOCK_ID)
        try:
            applied = await _fetch_applied_versions(conn)
            pending = pending_migrations(files, applied)
            if not pending:
                logger.info("Database is up to date (%d migrations applied)", len(files))
                return 0

            for migration in pending:
                logger.info("Applying migration %s", migration.name)
                sql = migration.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO app_schema_migrations (version) VALUES ($1)",
                        migration.stem,
                    )
            logger.info("Applied %d migration(s)", len(pending))
            return len(pending)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_ID)
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(run_migrations())
    except Exception:
        logger.exception("Migration run failed — refusing to start with a stale schema")
        sys.exit(1)


if __name__ == "__main__":
    main()
