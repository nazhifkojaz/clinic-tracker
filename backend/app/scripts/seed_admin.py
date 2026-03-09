"""Seed an initial admin user. Usage: uv run python -m app.scripts.seed_admin"""
import asyncio

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User, UserRole

# Default admin credentials - CHANGE IMMEDIATELY AFTER FIRST LOGIN!
ADMIN_EMAIL = "admin@clinic.local"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "System Admin"


async def seed() -> None:
    """Create the initial admin user if it doesn't exist."""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin user already exists: {ADMIN_EMAIL}")
            return

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name=ADMIN_NAME,
            role=UserRole.admin,
        )
        session.add(admin)
        await session.commit()
        print(f"Admin user created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("⚠ Change this password immediately after first login!")


if __name__ == "__main__":
    asyncio.run(seed())
