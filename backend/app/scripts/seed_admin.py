"""Seed an initial admin user. Usage: uv run python -m app.scripts.seed_admin"""

import asyncio
import os
import secrets

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User, UserRole

# Read from environment variables, with secure defaults
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@clinic.id")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
ADMIN_NAME = "Admin"

# Generate secure random password if not provided
_generated_password = None
if not ADMIN_PASSWORD:
    _generated_password = secrets.token_urlsafe(24)
    ADMIN_PASSWORD = _generated_password


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

        if _generated_password:
            print("⚠️  No SEED_ADMIN_PASSWORD environment variable set.")
            print(f"⚠️  Generated secure password: {ADMIN_PASSWORD}")
            print("⚠️  CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")
        else:
            print(f"Admin user created: {ADMIN_EMAIL}")
            print("⚠️  If this is production, ensure you've set a strong password!")


if __name__ == "__main__":
    asyncio.run(seed())
