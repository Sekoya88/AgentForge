import asyncio

from app.infrastructure.persistence.postgres.db import AsyncSessionLocal
from sqlalchemy import select

from app.infrastructure.persistence.postgres.models import ExecutionModel


async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ExecutionModel).limit(5))
        for row in res.scalars():
            msgs = row.output_messages
            if msgs:
                print(f"Exe {row.id}: {len(msgs)} messages. Roles: {[m['role'] for m in msgs]}")
            else:
                print(f"Exe {row.id}: no output")


if __name__ == "__main__":
    asyncio.run(main())
