import { expect, test } from "@playwright/test";

import { createE2eCourseIdentity } from "./fixtures";

/**
 * Belge silmenin çıkmazı gerçekten açılıyor mu?
 *
 * `questions.source_chunk_id` ON DELETE RESTRICT taşır: bir belgeden üretilmiş
 * soru havuzda durduğu sürece o belge silinemez ve API 409 ile şunu der:
 * "Önce ilgili soruları kaldırın." Soru silme UCU ve API testi vardı, ama
 * arayüzde hiçbir düğme onu çağırmıyordu — yani hata mesajı eğitmene
 * yapamayacağı bir şeyi öneriyordu. Bu test, çıkışın artık ekranda olduğunu
 * uçtan uca kanıtlar: 409 → arayüzden sil → belge silinir.
 *
 * "Reddet" bu çıkmazı AÇMAZ ve testin ikinci yarısı bunu ayrıca gösterir:
 * reddedilen soru satırı havuzda kalır, kısıt hâlâ yürürlüktedir.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const teacher = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "ayse@dogus.edu.tr",
  fullName: "Ayşe Hoca",
  role: "instructor",
};
const headers = { Authorization: `Bearer dev:${teacher.id}` };

test("soru silme, belge silmenin 409 çıkmazını arayüzden açar", async ({ page, request }) => {
  test.setTimeout(90_000);

  const courseResponse = await request.post(`${API}/courses`, {
    headers,
    data: createE2eCourseIdentity("SORU-SILME"),
  });
  expect(courseResponse.ok()).toBeTruthy();
  const course = await courseResponse.json();
  const base = `${API}/courses/${course.id}`;

  const topicResponse = await request.post(`${base}/topics`, {
    headers,
    data: { name: "Deadlock" },
  });
  expect(topicResponse.ok()).toBeTruthy();
  const topic = await topicResponse.json();

  const upload = await request.post(`${base}/documents`, {
    headers,
    multipart: {
      file: {
        name: "soru-silme.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# Deadlock\nDeadlock, iki veya daha fazla sürecin birbirini beklemesidir. " +
            "Coffman koşulları karşılıklı dışlama, elde tut ve bekle, kesintisizlik ve " +
            "döngüsel beklemedir.\n",
        ),
      },
    },
  });
  expect(upload.ok()).toBeTruthy();
  const { document } = await upload.json();

  await expect
    .poll(
      async () => {
        const response = await request.get(`${base}/documents`, { headers });
        const result = await response.json();
        return result.items[0]?.status;
      },
      { timeout: 25_000 },
    )
    .toBe("completed");

  const generated = await request.post(`${base}/questions/generate`, {
    headers,
    data: { topic_id: topic.id, count: 1, question_type: "mcq" },
  });
  expect(generated.ok()).toBeTruthy();
  const report = await generated.json();
  expect(report.questions.length).toBeGreaterThan(0);

  // Çıkmaz gerçekten var: belge, sorusu havuzdayken silinemiyor.
  const blocked = await request.delete(`${base}/documents/${document.id}`, { headers });
  expect(blocked.status()).toBe(409);
  expect(await blocked.text()).toContain("Önce ilgili soruları kaldırın");

  await page.addInitScript((user) => {
    localStorage.setItem("dou-synapse-token", `dev:${user.id}`);
    localStorage.setItem("dou-synapse-user", JSON.stringify(user));
  }, teacher);
  await page.goto(`/courses/${course.id}/questions`);

  // Reddetmek satırı havuzda bırakır: kısıt hâlâ yürürlükte olmalı.
  await page.getByRole("button", { name: "Reddet" }).click();
  await expect(page.getByRole("button", { name: "Reddedildi", exact: true })).toBeVisible();
  const stillBlocked = await request.delete(`${base}/documents/${document.id}`, { headers });
  expect(stillBlocked.status()).toBe(409);

  // Asıl çıkış: arayüzdeki silme, onaydan sonra satırı gerçekten kaldırır.
  await page.getByRole("button", { name: "Soruyu havuzdan sil" }).click();
  await page.getByRole("button", { name: "Kalıcı olarak sil" }).click();
  // Son soru kaldırılıp boş havuz çizildikten sonra da başarı duyurusu kalır.
  await expect(page.getByText(
    "Havuzda henüz soru yok. Yukarıdan bir konu seçip soru üretin; üretilen sorular taslak olarak buraya düşer.",
    { exact: true },
  )).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Soru havuzdan silindi" })).toBeVisible();

  await expect
    .poll(
      async () => {
        const response = await request.get(`${base}/questions`, { headers });
        const result = await response.json();
        return result.items.length;
      },
      { timeout: 15_000 },
    )
    .toBe(0);

  // Çıkmaz kapandı: belge artık silinebiliyor.
  const removed = await request.delete(`${base}/documents/${document.id}`, { headers });
  expect(removed.status()).toBe(204);
});
