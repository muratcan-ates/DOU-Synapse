"""Resmî sınav geri bildiriminin tek yayın kararı.

Blueprint sınavı için ``finish`` yalnız oturumu kapatır; puan, çözüm, rubrik ve
kaynak aynı anda açılmaz. Güvenli an oturum başlangıcında DB saatine göre
snapshot'lanan ``feedback_available_at`` değeridir. Practice ve blueprint'e bağlı
olmayan legacy sınavlar mevcut davranışı korur: bitişle birlikte açılır.
"""

from __future__ import annotations

from datetime import datetime

from app.models.assessment import ExamSession


def is_feedback_released(exam: ExamSession, *, now: datetime) -> bool:
    """Bu oturumun puan/çözüm zarfı gösterilebilir mi?

    Bitmemiş oturum hiçbir akışta sonuç göstermez. Blueprint oturumunda eksik
    schedule fail-closed'dur; migration öncesi tarihsel NULL satır kendiliğinden
    açılmaz. İstemci saati bu fonksiyona hiçbir çağrı yerinden verilmez.
    """

    if exam.finished_at is None:
        return False
    if exam.exam_version_id is None:
        return True
    return exam.feedback_available_at is not None and now >= exam.feedback_available_at


def pending_feedback_message(feedback_available_at: datetime | None) -> str:
    """Backend-owned, Türkçe bekleme metni; UI tarih politikasını yeniden kurmaz."""

    if feedback_available_at is None:
        return (
            "Sınavın kaydedildi. Bu eski oturum için güvenli sonuç yayın zamanı "
            "doğrulanamadığı için puan ve çözümler henüz açılmadı."
        )
    return (
        "Sınavın kaydedildi. Puan, çözümler ve kaynaklı geri bildirim sınav "
        f"penceresi tamamlandıktan sonra ({feedback_available_at.isoformat()}) açılacak."
    )
