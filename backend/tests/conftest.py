import pytest
import pytest_asyncio
from backend.app.database import init_db, AsyncSessionLocal
from backend.app.seeds.seed_data import seed_database

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)
