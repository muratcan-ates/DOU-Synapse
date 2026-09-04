# Repository findings and decisions

The repository already implements instructor uploads, RAG/Socratic course policy, approved question generation, four question types, blueprints and saved answers. 013 makes draft editing/classification visible. The missing student links were topic selection, open blueprint discovery and durable result/history navigation; adding another generator would duplicate existing capability.

Reading blueprint duration under student RLS fails after its enrollment window closes and falls back to global duration, shortening longer active exams and releasing assistant locks early. A narrow owned-session duration projection fixes visibility without exposing closed catalogs.

Existing grading accepted an absent/unknown dayanak_chunk_id while retaining a model score. Valid supplied source identity is a minimum necessary guard, not proof that the explanation semantically follows the source. Real-LLM calibration stays pending. Reuse the existing retry budget to avoid extra unbounded cost.

Independent review reproduced the same source gap in historical saved answers, including sources no longer readable. The projection now validates the source at display time and derives all visible aggregates from the same eligible results. This deliberately avoids a destructive data backfill. A hint could also wait for finish after loading stale session state; the user lock must precede the session load. Deadline checks after lock waits must use the current database wall clock, not PostgreSQL transaction-start now().
