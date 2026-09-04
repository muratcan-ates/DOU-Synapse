# Decisions

Main source and the unmerged 009-assessment-integrity branch were compared. The earlier branch already connects classification and includes larger official exam/feedback changes. This slice reuses the classification design and immutable-record test ideas; importing 78 files would change unrelated grading, runtime identity and feedback contracts.

Reuse existing Next.js16, React19, FastAPI, PostgreSQL/pgvector, type-specific payload validation, instructor membership dependencies and blueprint readiness. No framework or model change. A normal form is preferable to raw JSON because instructors must judge academic content, not internal chunk IDs. New authoring writes are controlled by deployment flag while legacy practice generation remains compatible.
