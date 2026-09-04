# Data model and invariants

No new table or classification column; reuse questions.payload, learning_outcome_id and difficulty. Migration0018 narrows UPDATE grants and adds a content/classification trigger independent from API validation.

- Course/topic/type/source identity cannot move through an update.
- Content/classification changes require OLD draft and no paper/session/answer references.
- Reviewed states cannot return to draft. Existing review transitions stay compatible where they do not change content.
- Assigned learning outcome belongs course and has null/matching topic.
- Teacher role remains course membership; platform admin conveys no instructor permission.

The existing outcome FK's ON DELETE SET NULL can meet the immutable classification guard: deleting an outcome used by a reviewed question must not silently rewrite its historical classification. This limitation is explicit; no delete-outcome endpoint is introduced.

Existing 0008 exam versions reference question IDs rather than payload snapshots, making draft-only immutable enforcement necessary before exposing an editor.

## Legacy payload metadata

Unknown existing payload fields are retained server-side even when omitted by an editing client; callers cannot add or change unknown values. Metadata-bearing structured lists keep count/order and row identity (MCQ key, rubric point), because old rubric rows have no stable identifier. The UI locks those legacy rubric structural/text controls, leaving weights editable. Ordinary generated rubrics remain fully editable.

## Integration compatibility

Existing blueprint test setup now classifies drafts before approving them. Existing UPDATE-RLS mutation proof changes review metadata on a visible approved question, so the new independent payload guard cannot mask a broken RLS policy. No production guard is relaxed.
