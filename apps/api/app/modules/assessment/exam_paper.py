"""Bir sınav oturumunun kâğıdı — soruların kimliği ve sırası (002 US3, T503).

`exam_sessions.question_ids`'in NOT NULL'ı 0008'de kalktı ve kâğıdın **iki kaynağı**
oldu:

- `exam_version_id IS NULL` → bugünkü self-servis prova. Kaynak `question_ids`;
  oturum açılırken sabitlenir.
- `exam_version_id IS NOT NULL` → blueprint sınavı. Kaynak `exam_items`, sırası
  `position`; `question_ids` NULL kalır.

Veritabanı bu ikiliği `exam_sessions_paper_source` kısıtıyla (`num_nonnulls(...) = 1`)
ifade edilemez kılıyor, ama **okuyan kod da tek yerden geçmeli**. Bu modül o tek yer.
Ayrı bir modül olmasının sebebi `exam_state.py`'nin işinin süre ve kilit olması
(Anayasa XI: bir dosya tek bir işi anlatır); kâğıdın kaynağı ayrı bir karar.

Bu fonksiyon yazılmadan `question_ids`'in NOT NULL'ını kaldırmak, ilk blueprint
oturumunda `TypeError` demekti: onu okuyan dört çağrı yeri de (`_session_out`,
`submit_answer`, `request_hint`, `finish_exam`) dizinin dolu olduğunu varsayıyordu.
Bu yüzden göç ve bu değişiklik aynı commit'te.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import ExamItem, ExamSession


async def paper_question_ids(session: AsyncSession, exam: ExamSession) -> list[UUID]:
    """Oturumun kâğıdındaki soru kimlikleri, öğrencinin göreceği sırayla.

    Prova akışında **sorgu koşmaz** — kâğıt zaten satırın üstündedir. Yalnız
    blueprint oturumları `exam_items`'a gider ve o da `exam_items_version_idx`
    üzerinden okunur.

    Sıra blueprint akışında anlamlıdır (`position` kâğıdın sırasıdır); prova
    akışında `question_ids` dizisinin kendi sırasıdır ve bugünkü davranış aynen
    korunur.
    """
    if exam.exam_version_id is None:
        return list(exam.question_ids or [])

    rows = await session.execute(
        select(ExamItem.question_id)
        .where(ExamItem.exam_version_id == exam.exam_version_id)
        .order_by(ExamItem.position)
    )
    return list(rows.scalars().all())


async def paper_question_weights(
    session: AsyncSession, exam: ExamSession
) -> dict[UUID, int] | None:
    """Kâğıttaki soru kimliklerini dondurulmuş puanlarına eşle.

    ``None`` legacy/self-servis kâğıdını bilinçli olarak ifade eder; bu
    akışta eşit ortalama kullanılır ve sorgu koşmaz. Blueprint oturumunda
    ise boş sözlük dahi ayrı bir sinyaldir: sürümün kalemi yoktur ve puanlama,
    cevaplanmış bir soru için ağırlık bulamazsa fail-closed davranabilir.

    Sıralama puanlama sözleşmesinin parçası değildir. Eşleme doğrudan
    ``question_id`` ile kurulur; cevapların geliş sırası bir sorunun puanını
    başka soruya taşıyamaz.
    """
    if exam.exam_version_id is None:
        return None

    rows = await session.execute(
        select(ExamItem.question_id, ExamItem.points).where(
            ExamItem.exam_version_id == exam.exam_version_id
        )
    )
    return {question_id: points for question_id, points in rows.all()}
