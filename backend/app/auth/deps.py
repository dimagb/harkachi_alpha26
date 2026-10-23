from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes import bearer
from app.auth.tokens import settings
from app.db import get_session
from app.errors import ApiErrorException
from app.models import Company, CompanyMember, User


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    unauthorized = ApiErrorException(
        401,
        "UNAUTHORIZED",
        "Требуется вход",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as error:
        raise unauthorized from error
    user = session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def bind_current_user(
    request: Request, user: Annotated[User, Depends(current_user)]
) -> None:
    request.state.user = user


def require_roles(*roles: str):
    def check_role(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise ApiErrorException(403, "FORBIDDEN", "Недостаточно прав")
        return user

    return check_role


def member_company(
    company_id: UUID, user: User, session: Session
) -> tuple[Company, CompanyMember]:
    result = session.execute(
        select(Company, CompanyMember)
        .join(CompanyMember, CompanyMember.company_id == Company.id)
        .where(Company.id == company_id, CompanyMember.user_id == user.id)
    ).first()
    if result is None:
        raise ApiErrorException(404, "NOT_FOUND", "Компания не найдена")
    return result[0], result[1]
