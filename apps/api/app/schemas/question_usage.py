"""Instructor-only metadata locating the papers that use a question."""

from uuid import UUID

from pydantic import BaseModel

from app.models.assessment import ExamVersionStatus


class QuestionExamUsageOut(BaseModel):
    id: UUID
    blueprint_id: UUID
    title: str
    version_id: UUID
    version_no: int
    status: ExamVersionStatus
