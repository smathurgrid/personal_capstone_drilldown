"""Database setup for authentication and account data."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.shared.config import settings


def _async_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)
    if raw_url.startswith("postgresql://") and "+asyncpg" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("sqlite://") and "+aiosqlite" not in raw_url:
        raw_url = raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return raw_url


engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global engine, SessionLocal
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for authentication")
    if engine is None:
        database_url = _async_database_url(settings.DATABASE_URL)
        connect_args = {}
        engine_args = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        else:
            engine_args.update(pool_size=5, max_overflow=10)
        engine = create_async_engine(database_url, connect_args=connect_args, **engine_args)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    return engine


async def get_db() -> AsyncSession:
    get_engine()
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required for authentication")
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from backend.auth.models import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_auth_schema(conn)


async def _migrate_auth_schema(conn) -> None:
    """Bring older local auth tables in line with the current User model."""
    dialect = conn.dialect.name
    if dialect == "postgresql":
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(120)"))
        await conn.execute(
            text(
                """
                UPDATE users
                SET name = split_part(email, '@', 1)
                WHERE name IS NULL OR name = ''
                """
            )
        )
        await conn.execute(text("ALTER TABLE users ALTER COLUMN name SET NOT NULL"))
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
        )
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"))
        await conn.execute(
            text(
                """
                UPDATE users
                SET password_hash = ''
                WHERE password_hash IS NULL
                """
            )
        )
        await conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL"))
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
        )
        await conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                """
            )
        )
        await conn.execute(
            text(
                """
                DO $$
                DECLARE
                    legacy_col record;
                BEGIN
                    FOR legacy_col IN
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'users'
                          AND is_nullable = 'NO'
                          AND column_name NOT IN (
                              'id',
                              'email',
                              'name',
                              'avatar_url',
                              'password_hash',
                              'is_active',
                              'created_at'
                          )
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE users ALTER COLUMN %I DROP NOT NULL',
                            legacy_col.column_name
                        );
                    END LOOP;
                END $$;
                """
            )
        )
        return

    if dialect == "sqlite":
        result = await conn.execute(text("PRAGMA table_info(users)"))
        columns = {row[1] for row in result.fetchall()}
        if "name" not in columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(120)"))
            await conn.execute(
                text(
                    """
                    UPDATE users
                    SET name = substr(email, 1, instr(email, '@') - 1)
                    WHERE name IS NULL OR name = ''
                    """
                )
            )
        if "password_hash" not in columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            await conn.execute(
                text(
                    """
                    UPDATE users
                    SET password_hash = ''
                    WHERE password_hash IS NULL
                    """
                )
            )
        if "avatar_url" not in columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
        if "is_active" not in columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
            )
        if "created_at" not in columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            )


async def close_db() -> None:
    global engine, SessionLocal
    if engine is not None:
        await engine.dispose()
    engine = None
    SessionLocal = None
