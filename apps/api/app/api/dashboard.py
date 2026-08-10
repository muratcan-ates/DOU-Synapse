"""Öğrenci ve eğitmenin aynı veri tabanından beslenen ürün ana sayfası."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.core.db import db_now
from app.core.errors import NotFoundError
from app.models.core import MembershipRole, Profile
from app.modules.assessment import exam_state
from app.schemas.dashboard import (
    DashboardCourse,
    DashboardOut,
    DashboardSummary,
    DashboardViewer,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DASHBOARD_QUERY = text(
    """
    SELECT
        c.id,
        c.code,
        c.title,
        m.role,
        (SELECT count(*) FROM documents AS d WHERE d.course_id = c.id)
            AS documents_total,
        (SELECT count(*) FROM documents AS d
         WHERE d.course_id = c.id AND d.status IN ('uploaded', 'processing'))
            AS documents_processing,
        CASE WHEN m.role = 'instructor' THEN
            (SELECT count(*) FROM documents AS d
             WHERE d.course_id = c.id AND d.status = 'failed')
        ELSE 0 END AS documents_failed,
        (SELECT count(*) FROM questions AS q WHERE q.course_id = c.id)
            AS questions_total,
        CASE WHEN m.role = 'instructor' THEN
            (SELECT count(*) FROM questions AS q
             WHERE q.course_id = c.id AND q.status = 'draft')
        ELSE 0 END AS draft_questions,
        (SELECT count(*) FROM exam_versions AS ev
         WHERE ev.course_id = c.id AND ev.status = 'published')
            AS published_exams,
        (SELECT avg(ms.score) FROM mastery AS ms
         WHERE ms.course_id = c.id AND ms.user_id = :user_id)
            AS mastery_score,
        greatest(
            (SELECT max(d.updated_at) FROM documents AS d WHERE d.course_id = c.id),
            (SELECT max(q.created_at) FROM questions AS q WHERE q.course_id = c.id),
            (SELECT max(es.started_at) FROM exam_sessions AS es
             WHERE es.course_id = c.id AND es.user_id = :user_id)
        ) AS last_activity_at
    FROM courses AS c
    JOIN course_memberships AS m ON m.course_id = c.id
    WHERE m.user_id = :user_id AND m.status = 'active'
    ORDER BY c.created_at DESC, c.id DESC
    """
)


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
) -> DashboardOut:
    profile = await session.get(Profile, principal.user_id)
    if profile is None:
        raise NotFoundError("Kullanıcı profili bulunamadı.")

    rows = (await session.execute(_DASHBOARD_QUERY, {"user_id": principal.user_id})).all()
    student_course_ids = {
        row.id for row in rows if MembershipRole(row.role) is MembershipRole.STUDENT
    }
    active_exams = (
        await exam_state.active_exam_sessions_by_course(
            session,
            user_id=principal.user_id,
            course_ids=student_course_ids,
            now=await db_now(session),
            settings=settings,
        )
        if student_course_ids
        else {}
    )

    courses: list[DashboardCourse] = []
    for row in rows:
        role = MembershipRole(row.role)
        assistant_locked = role is MembershipRole.STUDENT and row.id in active_exams
        courses.append(
            DashboardCourse(
                id=row.id,
                code=row.code,
                title=row.title,
                role=role,
                documents_total=int(row.documents_total),
                documents_processing=int(row.documents_processing),
                documents_failed=int(row.documents_failed),
                questions_total=int(row.questions_total),
                draft_questions=int(row.draft_questions),
                published_exams=int(row.published_exams),
                mastery_score=(float(row.mastery_score) if row.mastery_score is not None else None),
                last_activity_at=row.last_activity_at,
                assistant_locked=assistant_locked,
                assistant_lock_reason=(exam_state.EXAM_LOCK_REASON if assistant_locked else None),
                assistant_lock_message=(exam_state.EXAM_LOCK_MESSAGE if assistant_locked else None),
            )
        )
    instructor_courses = sum(1 for course in courses if course.role is MembershipRole.INSTRUCTOR)

    return DashboardOut(
        viewer=DashboardViewer(
            id=profile.id,
            email=profile.email,
            full_name=profile.full_name,
            is_platform_admin=bool(await session.scalar(text("SELECT app.is_platform_admin()"))),
        ),
        summary=DashboardSummary(
            total_courses=len(courses),
            instructor_courses=instructor_courses,
            student_courses=len(courses) - instructor_courses,
            action_items=sum(
                course.documents_processing + course.documents_failed + course.draft_questions
                for course in courses
                if course.role is MembershipRole.INSTRUCTOR
            ),
        ),
        courses=courses,
    )
