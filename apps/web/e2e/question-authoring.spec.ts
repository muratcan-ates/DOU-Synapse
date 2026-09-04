import { expect, test } from "@playwright/test";

import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacher = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "ayse@dogus.edu.tr",
  fullName: "Ayşe Hoca",
  role: "instructor",
};
const headers = { Authorization: `Bearer dev:${teacher.id}` };

test("eğitmen üretir, taslağı düzenler ve sınıflandırılmış soruyu yayımlar", async ({ page, request }, testInfo) => {
  test.setTimeout(90_000);
  const courseResponse = await request.post(`${API}/courses`, {
    headers, data: createE2eCourseIdentity("SORU-YAZIMI"),
  });
  expect(courseResponse.ok()).toBeTruthy();
  const course = await courseResponse.json();
  const base = `${API}/courses/${course.id}`;
  const topicResponse = await request.post(`${base}/topics`, {
    headers, data: { name: "Deadlock" },
  });
  expect(topicResponse.ok()).toBeTruthy();
  const topic = await topicResponse.json();
  const outcomeResponse = await request.post(`${base}/learning-outcomes`, {
    headers,
    data: { code: "LO-1", description: "Deadlock koşullarını açıklayabilir.", topic_id: topic.id },
  });
  expect(outcomeResponse.ok()).toBeTruthy();
  const outcome = await outcomeResponse.json();
  const upload = await request.post(`${base}/documents`, {
    headers,
    multipart: {
      file: {
        name: "question-authoring.md",
        mimeType: "text/markdown",
        buffer: Buffer.from("# Deadlock\nDeadlock, iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n"),
      },
    },
  });
  expect(upload.ok()).toBeTruthy();
  await expect.poll(async () => {
    const response = await request.get(`${base}/documents`, { headers });
    const result = await response.json();
    return result.items[0]?.status;
  }, { timeout: 25_000 }).toBe("completed");

  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, teacher);
  await page.goto(`/courses/${course.id}/questions`);
  await expect(page.getByLabel("Öğrenme çıktısı", { exact: true })).toBeVisible();
  await page.getByLabel("Konu", { exact: true }).selectOption(topic.id);
  await page.getByLabel("Kaç soru", { exact: true }).selectOption("1");
  await page.getByLabel("Öğrenme çıktısı", { exact: true }).selectOption(outcome.id);
  await page.getByLabel("Zorluk", { exact: true }).selectOption("medium");

  const generatedResponse = page.waitForResponse((response) =>
    response.url() === `${base}/questions/generate` && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Soru üret", exact: true }).click();
  const generated = await generatedResponse;
  expect(generated.ok()).toBeTruthy();
  const report = await generated.json();
  expect(report.questions).toHaveLength(1);
  const question = report.questions[0];
  expect(question.learning_outcome_id).toBe(outcome.id);
  expect(question.difficulty).toBe("medium");

  await page.getByRole("button", { name: "Taslağı düzenle", exact: true }).click();
  const editor = page.getByRole("form", { name: "Taslak soru düzenleme" });
  const editedStem = "Coffman koşullarından hangisi döngüsel beklemeyi tanımlar?";
  await editor.getByLabel("Soru metni", { exact: true }).fill(editedStem);
  const changedKey = (question.payload.options as Array<{ key: string }>).map((option) => option.key).find((key) => key !== question.payload.answer_key);
  expect(changedKey).toBeTruthy();
  await editor.getByLabel("Doğru şık", { exact: true }).selectOption(changedKey!);

  // The actual editing form must remain operable on a narrow screen in both themes.
  await page.setViewportSize({ width: 375, height: 812 });
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await expect(page.getByRole("button", { name: "Taslağı kaydet" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`authoring-375-${theme}.png`), fullPage: true });
  }

  const savedResponse = page.waitForResponse((response) =>
    response.url() === `${base}/questions/${question.id}/draft` && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Taslağı kaydet", exact: true }).click();
  const saved = await savedResponse;
  expect(saved.ok()).toBeTruthy();
  const updated = await saved.json();
  expect(updated.payload.stem).toBe(editedStem);
  expect(updated.payload.answer_key).toBe(changedKey);
  expect(Object.keys(updated.payload.distractor_sources).sort()).toEqual(
    (updated.payload.options as Array<{ key: string }>).map((option) => option.key).filter((key) => key !== changedKey).sort(),
  );
  expect(updated.source).toEqual(question.source);
  await expect(editor).not.toBeVisible();

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.emulateMedia({ colorScheme: "light" });
  const approval = page.waitForResponse((response) =>
    response.url() === `${base}/questions/${question.id}/approve`,
  );
  await page.getByRole("button", { name: "Onayla ve öğrenciye aç", exact: true }).click();
  expect((await approval).ok()).toBeTruthy();
  await expect(page.getByRole("button", { name: "Taslağı düzenle", exact: true })).toHaveCount(0);

  // Use the existing instructor blueprint screen: no privileged question seeding.
  await page.goto(`/courses/${course.id}/blueprints`);
  await page.getByRole("button", { name: "Yeni sınav kur", exact: true }).click();
  await page.getByLabel("Sınav adı", { exact: true }).fill("Düzenlenmiş soru sınavı");
  await page.getByLabel("Soru sayısı", { exact: true }).fill("1");
  await page.getByLabel("Kolay %", { exact: true }).fill("0");
  await page.getByLabel("Orta %", { exact: true }).fill("100");
  await page.getByLabel("Zor %", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Hücrelere aç", exact: true }).click();
  await page.getByRole("button", { name: "Sınavı kur", exact: true }).click();
  await page.getByRole("button", { name: "Yeni taslak sürüm", exact: true }).click();
  await page.getByRole("button", { name: "Kâğıdı düzenle", exact: true }).click();
  await page.getByRole("checkbox", { name: new RegExp(editedStem.replace("?", "\\?")) }).check();
  const paperSaved = page.waitForResponse((response) =>
    response.url().includes("/versions/") && response.url().endsWith("/items") &&
    response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Kâğıdı kaydet", exact: true }).click();
  expect((await paperSaved).ok()).toBeTruthy();
  const published = page.waitForResponse((response) =>
    response.url().endsWith("/publish") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Yayınla", exact: true }).click();
  expect((await published).ok()).toBeTruthy();
  await expect(page.getByText("1. sürüm yayında", { exact: true })).toBeVisible();

  const forbiddenRewrite = await request.post(`${base}/questions/${question.id}/draft`, {
    headers,
    data: { payload: { ...updated.payload, stem: "Onaydan sonra değiştirilemez" },
      learning_outcome_id: outcome.id, difficulty: "medium" },
  });
  expect(forbiddenRewrite.status()).toBe(409);
});
