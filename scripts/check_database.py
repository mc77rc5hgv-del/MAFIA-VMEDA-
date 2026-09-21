from __future__ import annotations

import asyncio
import json
import os

import asyncpg


async def main() -> None:
    database_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Database URL is missing")
    connection = await asyncpg.connect(database_url)
    try:
        rows = await connection.fetch(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        print(json.dumps({"tables": [row["tablename"] for row in rows]}))
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
