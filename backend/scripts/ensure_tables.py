"""Create any missing tables in the local SQLite database (non-destructive)."""

import asyncio

from app.infrastructure.database.models import Base
from app.infrastructure.database.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ensured.")


if __name__ == "__main__":
    asyncio.run(main())
