from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.models import User

settings = get_settings()


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(hours=settings.jwt_ttl_hours),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
