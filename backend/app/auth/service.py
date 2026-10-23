from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.errors import ApiErrorException
from app.auth.tokens import create_access_token, settings
from app.models import Company, CompanyMember, User
from app.security import verify_password


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str
    password: str


class UserBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    full_name: str
    role: Literal["CLIENT", "UNDERWRITER", "GUARANTOR"]


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserBrief


class CompanyBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    inn: str
    kind: Literal["IP", "OOO"]
    name: str


class Membership(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: CompanyBrief
    position: str
    can_sign: bool
    is_founder: bool


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: UserBrief
    companies: list[Membership]


def _brief(user: User) -> UserBrief:
    return UserBrief(id=user.id, full_name=user.full_name, role=user.role)


def login(session: Session, login: str, password: str) -> LoginResponse:
    user = session.scalar(select(User).where(User.login == login))
    if user is None or not verify_password(password, user.password_hash):
        raise ApiErrorException(401, "UNAUTHORIZED", "Неверный логин или пароль")
    return LoginResponse(
        access_token=create_access_token(user),
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
                    id=company.id, inn=company.inn, kind=company.kind, name=company.name
                ),
                position=membership.position,
                can_sign=membership.can_sign,
                is_founder=membership.is_founder,
            )
            for company, membership in rows
        ]
    return MeResponse(user=_brief(user), companies=memberships)
