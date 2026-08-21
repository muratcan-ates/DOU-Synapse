"""Giriş yapan kullanıcının düzenlenebilir profili."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select, text

from app.api.deps import PrincipalDep, SessionDep
from app.core.errors import NotFoundError
from app.models.core import Course, CourseMembership, MembershipStatus, Profile
from app.schemas.profile import ProfileMembershipOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/me/profile", tags=["profile"])


async def _profile_out(principal: PrincipalDep, session: SessionDep) -> ProfileOut:
    profile = await session.get(Profile, principal.user_id)
    if profile is None:
        raise NotFoundError("Kullanıcı profili bulunamadı.")

    rows = (
        await session.execute(
            select(
                Course.id,
                Course.code,
                Course.title,
                CourseMembership.role,
            )
            .join(CourseMembership, CourseMembership.course_id == Course.id)
            .where(
                CourseMembership.user_id == principal.user_id,
                CourseMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Course.code, Course.title)
        )
    ).all()

    return ProfileOut(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        created_at=profile.created_at,
        is_platform_admin=bool(await session.scalar(text("SELECT app.is_platform_admin()"))),
        memberships=[
            ProfileMembershipOut(
                course_id=row.id,
                course_code=row.code,
                course_title=row.title,
                role=row.role,
            )
            for row in rows
        ],
    )


@router.get("", response_model=ProfileOut)
async def get_my_profile(principal: PrincipalDep, session: SessionDep) -> ProfileOut:
    return await _profile_out(principal, session)


@router.patch("", response_model=ProfileOut)
async def update_my_profile(
    payload: ProfileUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ProfileOut:
    """Yalnız ad soyadı değiştirir; e-posta kimlik sağlayıcısına aittir."""
    profile = await session.get(Profile, principal.user_id)
    if profile is None:
        raise NotFoundError("Kullanıcı profili bulunamadı.")
    profile.full_name = payload.full_name
    await session.flush()
    return await _profile_out(principal, session)
