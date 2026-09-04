# Local acceptance walkthrough

Apply all sorted migrations including0018 and0019 to an isolated database. Start API with fake/hash providers for synthetic validation and STUDENT_ASSESSMENT_WORKSPACE_ENABLED=true; never infer real-model quality from this mode.

1. Instructor uploads a small Markdown/PDF source, creates topic/outcome and generates questions. Edit/classify draft with013, approve, create and publish a blueprint whose window is open.
2. Student opens Ders → Sınav. Choose a topic and start an alıştırma. Submit one answer; inspect the source-backed feedback.
3. Return to Oturumlarım. Start a catalog exam, reload, return via Devam et; remaining time is not reset.
4. During timed exam, historical solutions and practice help are locked. Finish and reopen via Sonucu gör. Missing/incorrect answer explanation links to actual source where available.
5. Repeat on narrow mobile width and dark theme. Disable workspace flag: legacy start/resume remains, new API surfaces unavailable.

Automated exact commands and actual outcomes are recorded in verification.md once executed.
