"""Update admin email to a valid domain for testing."""

import asyncio

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.user import User

OLD_EMAIL = "admin@clinic.local"
NEW_EMAIL = "admin@dashko.dev"


async def update_email() -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == OLD_EMAIL))
        admin = result.scalar_one_or_none()

        if admin:
            admin.email = NEW_EMAIL
            await session.commit()
            print(f"Admin email updated: {OLD_EMAIL} -> {NEW_EMAIL}")
        else:
            print(f"Admin user not found: {OLD_EMAIL}")


if __name__ == "__main__":
    asyncio.run(update_email())
