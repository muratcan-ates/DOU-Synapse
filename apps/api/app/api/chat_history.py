"""Sohbet kalıcılaştırması: oturum yükleme/açma, Sokratik durum, mesaj ekleme.

`app/api/chat.py`'den taşındı (modülerizasyon v2, PR 11). Davranış birebir aynı.
Bu yardımcılar api katmanında kalır: `CourseContext` (deps) ve istek zarfı
(`ChatRequest`) ile konuşurlar; alan servisleri (`modules/agent/answers.py`)
bunları hiç görmez.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat_cache import _audience, _citation_to_json
from app.api.deps import CourseContext
from app.contracts import GeneratedAnswer
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.modules.assessment import socratic
from app.schemas.chat import ChatRequest

logger = get_logger("app.chat")


def _is_first_turn(chat_session: ChatSession) -> bool:
    return "socratic" not in chat_session.state


def _stored_state(chat_session: ChatSession) -> socratic.SocraticState:
    return socratic.SocraticState.from_json(chat_session.state.get("socratic"))


async def _load_or_create_session(
    session: AsyncSession, context: CourseContext, payload: ChatRequest
) -> ChatSession:
    if payload.session_id is None:
        chat_session = ChatSession(
            course_id=context.course_id,
            user_id=context.user_id,
            mode=payload.mode,
            audience=_audience(context),
            state={},
            title=payload.question.strip()[:80],
        )
        session.add(chat_session)
        await session.flush()
        return chat_session

    # Ayrı ad: yukarıdaki dalda `chat_session` ChatSession, burada `get()`
    # ChatSession | None döndürüyor. Aynı ada yazmak mypy'ı kırıyordu ve
    # okuyucuya da iki farklı şeyin aynı değişken olduğunu ima ediyordu.
    existing = await session.get(ChatSession, payload.session_id)
    if existing is None or existing.course_id != context.course_id:
        raise NotFoundError("Sohbet oturumu bulunamadı.")
    if existing.mode is not payload.mode:
        # Mod ortasında değiştirilemez: Sokratik durum moda aittir, QA'ya geçip geri
        # dönmek merdiveni sıfırlamanın kolay yolu olurdu.
        raise ValidationError(
            "Bu oturum farklı bir modda başlatılmış. Yeni mod için yeni bir sohbet aç."
        )
    if existing.audience is not _audience(context):
        raise ConflictError(
            "Ders rolün değiştiği için bu sohbet sürdürülemez. Yeni bir sohbet aç.",
            code="session_audience_changed",
        )
    return existing


async def _opening_question(
    session: AsyncSession, chat_session: ChatSession, *, fallback: str
) -> str:
    """Oturumu açan kullanıcı mesajı — Sokratik merdivenin üzerinde ilerlediği soru.

    Ayrı bir sütunda kopyalanmıyor, ilk mesajdan okunuyor: aynı veriyi iki yerde
    tutmak, birinin güncellenip diğerinin unutulduğu bir hata sınıfı açardı
    (Anayasa XI). `chat_messages` üzerinde (session_id, created_at, seq) indeksi var.

    NOT (gruba iletildi): öğrencinin son denemesi üretime geçirilemiyor çünkü
    `contracts.Generator.generate` imzasında böyle bir alan yok. Kademe metni bu
    yüzden denemeye değil yalnız kademeye ve soruya göre şekilleniyor.
    """
    content = await session.scalar(
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == chat_session.id,
            ChatMessage.role == ChatRole.USER,
        )
        .order_by(ChatMessage.created_at, ChatMessage.seq)
        .limit(1)
    )
    return content or fallback


async def _record_turn(
    session: AsyncSession,
    context: CourseContext,
    chat_session: ChatSession,
    answer: GeneratedAnswer,
    decision: socratic.SocraticDecision | None,
) -> None:
    """Sokratik durumu kalıcılaştırır ve kademe geçişini olay olarak loglar.

    Durum **yalnız gerçekten ipucu servis edildiyse** yazılır. Kanıt eşiği aşılamadıysa
    ya da soru kapsam dışıysa kullanıcı hiçbir ipucu almamıştır; o turu ilerleme saymak,
    öğrenciyi hiç yardım almadığı bir kademeye taşırdı. Canlı koşuda gözlendi: materyali
    olmayan bir soruya yapılan deneme, merdiveni sessizce bir kademe yukarı itiyordu.

    Ölçü olarak `answer.socratic_stage` kullanılıyor çünkü bu alan tam olarak "bu turda
    şu kademenin ipucu gösterildi" demektir; abstention yollarında None kalır.
    """
    if decision is None or answer.socratic_stage is None:
        return

    chat_session.state = {**chat_session.state, "socratic": decision.state.to_json()}

    if decision.transition is not None:
        # FR-014: her kademe geçişi kayıt altına alınır. İki yerde birden — durum
        # jsonb'sinde (kalıcı, sorgulanabilir) ve yapılandırılmış logda (zaman serisi).
        logger.info(
            "sokratik kademe ilerledi",
            extra={
                "context": {
                    "course_id": str(context.course_id),
                    "session_id": str(chat_session.id),
                    "from": decision.transition.from_stage.value,
                    "to": decision.transition.to_stage.value,
                    "attempt": decision.attempt_kind.value,
                }
            },
        )
    elif decision.refusal_notice is not None:
        logger.info(
            "sokratik kademe korundu",
            extra={
                "context": {
                    "course_id": str(context.course_id),
                    "session_id": str(chat_session.id),
                    "stage": decision.stage.value,
                    "attempt": decision.attempt_kind.value,
                    "refusals": decision.state.refusals,
                }
            },
        )


async def _append_messages(
    session: AsyncSession,
    context: CourseContext,
    chat_session: ChatSession,
    turn_text: str,
    answer: GeneratedAnswer,
    claims: dict[UUID, str],
) -> ChatMessage:
    session.add(
        ChatMessage(
            session_id=chat_session.id,
            course_id=context.course_id,
            role=ChatRole.USER,
            content=turn_text,
            citations=[],
            status=None,
            socratic_stage=None,
            seq=0,
        )
    )
    assistant = ChatMessage(
        session_id=chat_session.id,
        course_id=context.course_id,
        role=ChatRole.ASSISTANT,
        content=answer.text,
        citations=[_citation_to_json(c, claims.get(c.chunk_id, "")) for c in answer.citations],
        status=answer.status,
        socratic_stage=answer.socratic_stage,
        seq=1,
    )
    session.add(assistant)
    await session.flush()
    return assistant
