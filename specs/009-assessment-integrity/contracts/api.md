# API Sözleşmesi

## Hazırlık kontrolü

`GET /health/ready`, veritabanı erişimine ek olarak gerçek API bağlantı kimliğini
doğrular. `checks.database_role=ok` yalnız `session_user=dou_api_runtime` olduğunda
verilir. Yanlış DSN, superuser veya pooler'ın yalnız `SET ROLE` taklidi 503
`status=degraded` üretir; aday revizyona trafik verilmez.

## Soru üretimi

`POST /courses/{course_id}/questions/generate`

İstek additive alanları:

```json
{
  "topic_id": "uuid",
  "question_type": "mcq",
  "purpose": "assessment",
  "learning_outcome_id": "uuid",
  "difficulty": "medium"
}
```

`purpose` verilmezse geriye uyumlu `practice`; response `QuestionOut.purpose` alanını
her zaman taşır. `learning_outcome_id` ve `difficulty` birlikte verilir veya ikisi de
boş bırakılır. Student bu uca/list ucuna erişemez.

`PATCH /courses/{course_id}/questions/{question_id}/classification` yalnız taslak
sorunun sınıflandırmasını değiştirir:

```json
{
  "learning_outcome_id": "uuid",
  "difficulty": "medium"
}
```

Başka ders çıktısı 404, açık konu uyuşmazlığı 422, terminal soru 409
`question_immutable`; tanımsız alan 422'dir.

Sınıflandırılmamış `assessment` taslağını onaylama 409
`question_classification_required` döndürür.

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
