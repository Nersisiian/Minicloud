import asyncio
import sys

from core.security import get_password_hash
from db.base import async_session_factory
from db.models import User


async def create_admin():
    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        admin = User(
            username="admin",
            hashed_password=get_password_hash("admin"),
            email="admin@minicloud.local",
        )
        session.add(admin)
        await session.commit()
        print("Admin user created (username: admin, password: admin)")


if __name__ == "__main__":
    asyncio.run(create_admin())
