"""Ders ve üyelik uçları."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    CourseInstructorDep,
    CourseMemberDep,
    PrincipalDep,
    SessionDep,
)
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.core import Course, CourseMembership, MembershipRole, MembershipStatus, Profile
from app.schemas.course import (
    CourseCreate,
    CourseOut,
    CourseWithRole,
    MembershipCreate,
    MembershipOut,
)

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseWithRole])
async def list_my_courses(principal: PrincipalDep, session: SessionDep) -> list[CourseWithRole]:
    """Kullanıcının aktif üyeliği olan dersler."""
    result = await session.execute(
        select(Course, CourseMembership.role)
        .join(CourseMembership, CourseMembership.course_id == Course.id)
        .where(
            CourseMembership.user_id == principal.user_id,
            CourseMembership.status == MembershipStatus.ACTIVE,
        )
        .order_by(Course.created_at.desc())
    )
    return [
        CourseWithRole(**CourseOut.model_validate(course).model_dump(), role=role)
        for course, role in result.all()
    ]


@router.post("", response_model=CourseWithRole, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate, principal: PrincipalDep, session: SessionDep
) -> CourseWithRole:
    """Ders oluşturur ve oluşturana aynı işlemde eğitmen üyeliği verir.

    İki kayıt tek işlemde yazılır; aksi halde sahipsiz (kimsenin göremediği) bir ders
    kalabilirdi.
    """
    try:
        course_id = await session.scalar(
            text("SELECT app.create_course(:code, :title)"),
            {"code": payload.code, "title": payload.title},
        )
    except IntegrityError as exc:
        raise ConflictError(f"'{payload.code}' kodlu bir ders zaten var.") from exc

    course = await session.get(Course, course_id)
    if course is None:  # pragma: no cover - fonksiyon üyeliği aynı işlemde yazar
        raise NotFoundError("Ders oluşturuldu ancak okunamadı.")

    return CourseWithRole(
        **CourseOut.model_validate(course).model_dump(), role=MembershipRole.INSTRUCTOR
    )


@router.get("/{course_id}", response_model=CourseWithRole)
async def get_course(context: CourseMemberDep, session: SessionDep) -> CourseWithRole:
    course = await session.get(Course, context.course_id)
    if course is None:  # pragma: no cover - üyelik doğrulandıysa ders vardır
        raise NotFoundError("Ders bulunamadı.")
    return CourseWithRole(**CourseOut.model_validate(course).model_dump(), role=context.role)


@router.get("/{course_id}/members", response_model=list[MembershipOut])
async def list_members(context: CourseInstructorDep, session: SessionDep) -> list[MembershipOut]:
    result = await session.execute(
        select(CourseMembership, Profile)
        .join(Profile, Profile.id == CourseMembership.user_id)
        .where(CourseMembership.course_id == context.course_id)
        .order_by(CourseMembership.role, Profile.email)
    )
    return [
        MembershipOut(
            user_id=membership.user_id,
            email=profile.email,
            full_name=profile.full_name,
            role=membership.role,
            status=membership.status,
        )
        for membership, profile in result.all()
    ]


@router.post(
    "/{course_id}/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED
)
async def add_member(
    payload: MembershipCreate, context: CourseInstructorDep, session: SessionDep
) -> MembershipOut:
    """Derse üye ekler. Kullanıcının sistemde kayıtlı olması gerekir.

    E-postadan kullanıcı bulmak profiles üzerindeki RLS'i aşmayı gerektirdiğinden işlem,
    yetki kontrolünü kendi içinde yapan `app.add_course_member()` fonksiyonuna devredilir.
    """
    row = (
        await session.execute(
            text(
                "SELECT result, user_id FROM app.add_course_member("
                ":course_id, :email, CAST(:role AS membership_role))"
            ),
            {
                "course_id": context.course_id,
                "email": payload.email,
                "role": payload.role.value,
            },
        )
    ).one()

    if row.result == "no_user":
        raise NotFoundError(
            "Bu e-posta ile kayıtlı kullanıcı yok. Kullanıcının önce giriş yapması gerekir."
        )
    if row.result == "already_member":
        raise ConflictError("Bu kullanıcı zaten derse kayıtlı.")

    profile = await session.get(Profile, row.user_id)
    if profile is None:  # pragma: no cover - üyelik yazıldıysa profil görünür
        raise NotFoundError("Kullanıcı bulunamadı.")

    return MembershipOut(
        user_id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        role=payload.role,
        status=MembershipStatus.ACTIVE,
    )


@router.delete("/{course_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_member(user_id: UUID, context: CourseInstructorDep, session: SessionDep) -> None:
    """Üyeliği iptal eder (kayıt silinmez, geçmiş korunur)."""
    if user_id == context.user_id:
        raise ValidationError("Kendi eğitmen üyeliğinizi kaldıramazsınız.")

    membership = (
        await session.execute(
            select(CourseMembership).where(
                CourseMembership.course_id == context.course_id,
                CourseMembership.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Bu kullanıcı derse kayıtlı değil.")

    membership.status = MembershipStatus.REVOKED
    await session.flush()
