"""Deterministic oracle set for acceptance scoring of L2 code grading cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.models.assessment import QuestionType


@dataclass(frozen=True)
class OracleAnswer:
    anchor: str
    answer: str
    expected_score: int
    expected_missing_points: list[str]


@dataclass(frozen=True)
class OracleCase:
    case_id: str
    question_type: QuestionType
    source_id: UUID
    source_name: str
    source_text: str
    payload: dict[str, Any]
    answers: tuple[OracleAnswer, ...]


CODE_TRACE_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        case_id="GRADE-TRACE-01",
        question_type=QuestionType.CODE_TRACE,
        source_id=UUID("3f2bd8f0-8f7b-4b7c-b6ec-2a4a0f6fc5f1"),
        source_name="fork_example.c",
        source_text=(
            "fork() çağrısı bir çocuk süreç üretir. Çocukta return değerı 0, ebeveynde "
            "çocuğun pid değeridir."
        ),
        payload={
            "language": "C",
            "code": "pid_t pid = fork();\nif (pid == 0) { return 0; } else { waitpid(pid, NULL, 0); }",
            "prompt": "fork sonrası pid değerleri nasıl döner?",
            "answer_key": "Child returns 0, parent returns child pid.",
            "explanation": "fork_return ve waitpid davranışını takip eder.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer="Çocukta 0, ebeveynde çocuğun pid'i döner ve ebeveyn waitpid ile çocuğu bekler.",
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="İki süreçte de aynı pid döner.",
                expected_score=50,
                expected_missing_points=["fork dönüş değerini ayırt etme"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Çocuğa ebeveyn pid'i döner, ebeveyn hiçbir şey döndürmez.",
                expected_score=0,
                expected_missing_points=["fork ve waitpid modelini kavrama"],
            ),
        ),
    ),
    OracleCase(
        case_id="GRADE-TRACE-02",
        question_type=QuestionType.CODE_TRACE,
        source_id=UUID("67b9c9f5-6d70-4a2d-97f0-2d7b4d3b0ff9"),
        source_name="thread_pool.py",
        source_text=(
            "Worker thread çalışmayı bitirdikten sonra queue'dan sonraki işi alır; "
            "kapatma işaretini sadece kuyruk boştayken güvenle işler."
        ),
        payload={
            "language": "Python",
            "code": "while True:\n    task = queue.get()\n    if task is None: break\n    execute(task)\n    queue.task_done()",
            "prompt": "Thread havuzu kapanış durumunda ne olur?",
            "answer_key": "None işareti alınırsa güvenli şekilde döngü sona erer.",
            "explanation": "Sonsuz döngü koşulları kapatma şartına göre kontrol edilir.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer="Thread, sentinel görev almazsa kuyruğu beklemeye devam eder; sentinel ile görünürse güvenli çıkar.",
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="Thread doğrudan task listesinin başlangıcını sonlandırır.",
                expected_score=50,
                expected_missing_points=["kapanma işaretinin rolü"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Thread task bitirir bitirmez queue'u siliyor gibi davranır.",
                expected_score=0,
                expected_missing_points=["thread pool sonlandırma akışı"],
            ),
        ),
    ),
    OracleCase(
        case_id="GRADE-TRACE-03",
        question_type=QuestionType.CODE_TRACE,
        source_id=UUID("9af8e2cb-bbb5-4c6f-a4c6-4d7e5f8f2bb7"),
        source_name="pipe_shell.c",
        source_text=(
            "pipe açıldıktan sonra hangi süreç hangi ucu kapatırsa deadlock önlenir; "
            "yanlış kapatma bloklanma yaratır."
        ),
        payload={
            "language": "C",
            "code": "int p[2]; pipe(p); pid = fork(); if (pid == 0) { close(p[1]); dup2(p[0],0); ... }",
            "prompt": "fork sonrası pipe uçları kapatılmadığında olası sonuç ne olur?",
            "answer_key": "Yanlış kapanmayan uç, bloklama veya beklenmeyen EOF davranışı üretir.",
            "explanation": "Pipe uçlarının kapanma sırası iletişim kapanışını doğru belirler.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer="Kullanılmayacak uçlar kapatılmazsa karşı süreç sonlanmış olsa bile pipe açık kalıp bekleme doğurur.",
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="Pipe yalnızca write tarafından kapatılırsa yeterlidir.",
                expected_score=50,
                expected_missing_points=["read/write tarafı kapanma simetrisi"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Pipe açılınca hiçbir uç kapanmazsa sorun olmaz.",
                expected_score=0,
                expected_missing_points=["pipe yaşam döngüsü mantığı"],
            ),
        ),
    ),
)


BUG_HUNT_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        case_id="GRADE-BUG-01",
        question_type=QuestionType.BUG_HUNT,
        source_id=UUID("a0f4a0b3-9a34-4d80-ae17-7dd1f6ad1cb4"),
        source_name="producer_consumer.py",
        source_text=(
            "Üretici-tüketici senaryosunda mutex önce alınırsa ve semafor hatası varsa "
            "hem producer hem consumer birbirini bekletebilir."
        ),
        payload={
            "language": "Python",
            "code": "empty_sem.wait(); mutex.acquire(); buffer.append(x); mutex.release(); full_sem.release()",
            "prompt": "Aşağıdaki kritik akışta döngüsel bekleme nasıl çözülür?",
            "answer_key": {
                "line": 1,
                "bug_type": "Deadlock/Race ordering",
                "fix_summary": "Semafor beklemesi ile mutex edinimini doğru sırada düzenleyin",
            },
            "explanation": "Lock acquisition order must be fixed.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer=(
                    "empty semaforu alınmadan önce mutex tutulmalı değildir; önce semaforlarla bloklama, sonra "
                    "mutex edinimi ve kritik bölüm korunmalıdır."
                ),
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="Mutex tek başına yeterli ve sıralama önemli değildir.",
                expected_score=50,
                expected_missing_points=["semafor-mutex sırası"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Hata yalnız eksik bir print satırındadır.",
                expected_score=0,
                expected_missing_points=["kritik bölümün sıralama hatası"],
            ),
        ),
    ),
    OracleCase(
        case_id="GRADE-BUG-02",
        question_type=QuestionType.BUG_HUNT,
        source_id=UUID("f3ad3a95-b3d7-4b5e-a2a5-e5b0c7d53f44"),
        source_name="reader_writer.py",
        source_text=(
            "Reader/writer korumasında sayaç güncellemesi mutex olmadan ise birden fazla thread aynı anda "
            "kısıtlar ve race condition oluşturabilir."
        ),
        payload={
            "language": "Python",
            "code": "read_count += 1\nif read_count == 1: resource_lock.acquire()\nread_count -= 1",
            "prompt": "Bu kod parçasında hangi sıradaki koruma eksiktir?",
            "answer_key": {
                "line": 1,
                "bug_type": "Data race",
                "fix_summary": "shared counter için tek bir mutex ekleyin",
            },
            "explanation": "Sayaç işlemleri atomik korunmalıdır.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer="read_count güncellemesi mutex ile korunmalı, ardından ilk okuyucu/son okuyucu geçişi kontrol edilmelidir.",
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="Sadece resource_lock'i bir kez ekleyip okumaya geçmek yeterlidir.",
                expected_score=50,
                expected_missing_points=["counter increment/decrement kritik alanı"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Bu kodda hata yoktur, sırada sadece zamanlama vardır.",
                expected_score=0,
                expected_missing_points=["paylaşılan sayaç koruması"],
            ),
        ),
    ),
    OracleCase(
        case_id="GRADE-BUG-03",
        question_type=QuestionType.BUG_HUNT,
        source_id=UUID("8b79d4f7-0d44-4df4-9f8c-9e6f6d6d4e8a"),
        source_name="page_replacement.py",
        source_text=(
            "Random replacement gerçek sayfa çalıştırma simülasyonunda yanlış sonuç verir; geçmiş referans bilgisi "
            "gerekli politikanın anahtarıdır."
        ),
        payload={
            "language": "Python",
            "code": "if len(frames) < cap: frames.append(page)\nelse: frames[random.choice(frames)] = page",
            "prompt": "Simülasyon yanlışlığı hangi öneriyle düzeltilir?",
            "answer_key": {
                "line": 2,
                "bug_type": "Wrong replacement policy",
                "fix_summary": "Rastgele seçim yerine policy tabanlı seçim uygulanmalı",
            },
            "explanation": "Politika en az kullanılma bilgisini izlemelidir.",
        },
        answers=(
            OracleAnswer(
                anchor="correct",
                answer="LRU/second-chance benzeri politika kullanılmalı; rastgele seçim yerine geçmiş erişim bilgisiyle seçim yapılmalıdır.",
                expected_score=100,
                expected_missing_points=[],
            ),
            OracleAnswer(
                anchor="partial",
                answer="Kapasiteyi artırmak tek başına sorunu çözmez.",
                expected_score=40,
                expected_missing_points=["policy seçim mantığı"],
            ),
            OracleAnswer(
                anchor="incorrect",
                answer="Yalnız dosyanın başına line numarası eklemek bu hatayı kapatır.",
                expected_score=0,
                expected_missing_points=["değiştirme algoritması"],
            ),
        ),
    ),
)
