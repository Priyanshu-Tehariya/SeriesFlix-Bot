import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from bot.config import settings

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        print("Resetting file_requests auto-increment counter...")
        await conn.execute(text("TRUNCATE TABLE file_requests RESTART IDENTITY CASCADE;"))
        await conn.commit()
        print("Successfully truncated file_requests and reset sequence to 1.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
