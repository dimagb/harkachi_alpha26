from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import create_access_token, settings
from app.errors import ApiErrorException
from app.models import Company, CompanyMember, User
from app.schemas.api import (
    CompanyBrief,
    LoginResponse,
    Membership,
    MeResponse,
    UserBrief,
)
from app.security import verify_password

DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$GxCqFYBHRaeenn+hB4rnKg$"
    "WuLbMZZLvWbS0rIbRGGK0xVUkERl2w6AKbX1PfSgt94"
)


def _brief(user: User) -> UserBrief:
    return UserBrief(id=str(user.id), full_name=user.full_name, role=user.role)


def login(session: Session, login: str, password: str) -> LoginResponse:
    user = session.scalar(select(User).where(User.login == login))
    verified = verify_password(
        password, DUMMY_HASH if user is None else user.password_hash
    )
    if user is None or not verified:
        raise ApiErrorException(401, "UNAUTHORIZED", "Неверный логин или пароль")
    return LoginResponse(
        access_token=create_access_token(user),
        token_type="bearer",
        expires_in=settings.jwt_ttl_hours * 3600,
        user=_brief(user),
    )


def me(session: Session, user: User) -> MeResponse:
    memberships = []
    if user.role != "UNDERWRITER":
        rows = session.execute(
            select(Company, CompanyMember)
            .join(CompanyMember, CompanyMember.company_id == Company.id)
            .where(CompanyMember.user_id == user.id)
            .order_by(Company.name)
        )
        memberships = [
            Membership(
                company=CompanyBrief(
                    id=str(company.id),
                    inn=company.inn,
                    kind=company.kind,
                    name=company.name,
                ),
                position=membership.position,
                can_sign=membership.can_sign,
                is_founder=membership.is_founder,
            )
            for company, membership in rows
        ]
    return MeResponse(user=_brief(user), companies=memberships)
