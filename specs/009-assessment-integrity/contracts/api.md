# API Sözleşmesi

## Soru üretimi

`POST /courses/{course_id}/questions/generate`

İstek additive alanı:

```json
{
  "topic_id": "uuid",
  "question_type": "mcq",
  "purpose": "practice"
}
```

`purpose` verilmezse geriye uyumlu `practice`; response `QuestionOut.purpose` alanını
her zaman taşır. Student bu uca/list ucuna erişemez.

## Sürüm kalemleri

`POST /courses/{course_id}/blueprints/{blueprint_id}/versions/{version_id}/items`

Practice-purpose soru için 409 `question_not_assessment`; terminal question mutation
için 409 `question_immutable`.

## Sınav başlangıcı

`POST /courses/{course_id}/exams`

- `blueprint_id` + flag false → 503 `assessment_blueprint_disabled`.
- `blueprint_id` + closes_at null → 409 `assessment_feedback_schedule_missing`.
- active exam + yeni practice/legacy start → 403 `exam_in_progress`.

Blueprint response additive alanları:

```json
{
  "feedback_released": false,
  "feedback_available_at": "2026-08-20T09:30:00Z",
  "score": null
}
```

## Bitiş ve sonuç

`POST /courses/{course_id}/exams/{session_id}/finish` oturumu bir kez kapatır.

`GET /courses/{course_id}/exams/{session_id}/results` idempotent sonuç okumasıdır.

Her ikisi `ExamFinishOut` döndürür:

```json
{
  "session_id": "uuid",
  "score": null,
  "answered_count": 2,
  "unanswered_count": 1,
  "ungraded_count": 0,
  "feedback_released": false,
  "feedback_available_at": "2026-08-20T09:30:00Z",
  "message": "Sınavın kaydedildi. Sonuç ve çözümler belirtilen zamanda açılacak.",
  "results": []
}
```

Yayın sonrası aynı GET, weighted `score`, `feedback_released=true` ve çözüm/rubrik/
source içeren `results` döndürür. Yayın öncesi endpoint bu verileri DB'den yüklemez.

