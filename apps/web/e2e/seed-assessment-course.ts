import { expect, type APIRequestContext } from "@playwright/test";
import { student, teacherHeaders } from "./worker-fixture";
import { createE2eCourseIdentity } from "./fixtures";

const API = process.env.E2E_API_URL ?? "http://localhost:8000";

/** Gerçek yerel API ile sentetik materyal, onaylı soru ve ders üyeliği kurar. */
export async function seedAssessmentCourse(request: APIRequestContext) {
  const post = async (path: string, data: unknown) => {
    const response = await request.post(`${API}${path}`, { headers: teacherHeaders, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const course = await post("/courses", createE2eCourseIdentity("AG-KORUMASI"));
  const base = `/courses/${course.id}`;
  await post(`${base}/members`, { email: student.email, role: "student" });
  const topic = await post(`${base}/topics`, { name: "Deadlock" });
  const upload = await request.post(`${API}${base}/documents`, { headers: teacherHeaders,
    multipart: { file: { name: "network-guards.md", mimeType: "text/markdown",
      buffer: Buffer.from("# Deadlock\nDeadlock iki veya daha fazla sürecin birbirini beklemesidir. Coffman koşulları karşılıklı dışlama, tut ve bekle, kesintisizlik ve dairesel beklemedir.\n"),
    } },
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  await expect.poll(async () => {
    const response = await request.get(`${API}${base}/documents`, { headers: teacherHeaders });
    expect(response.ok()).toBeTruthy(); return (await response.json()).items[0]?.status;
  }, { timeout: 25_000 }).toBe("completed");
  const generated = await post(`${base}/questions/generate`, { topic_id: topic.id, count: 1, question_type: "mcq" });
  expect(generated.questions).toHaveLength(1);
  const question = generated.questions[0];
  await post(`${base}/questions/${question.id}/approve`, {});
  return { course, base, question };
}
