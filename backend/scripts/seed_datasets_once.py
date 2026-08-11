import asyncio

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.seed.seed_report_datasets import seed_report_datasets


async def main() -> None:
    async with SessionLocal() as session:
        await seed_report_datasets(session)


if __name__ == "__main__":
    asyncio.run(main())
