/**
 * Oturum kancasının saf kararları.
 *
 * Kancanın kendisi React ister; buradaki iki kural DOM'suz sınanır çünkü
 * bozulmaları sessizdir: yanlış oturum açmak sunucudan 4xx döner ve kullanıcı
 * anlamsız bir hata görür, gereksiz liste tazelemesi ise Anayasa XI'e aykırı
 * fazladan GET üretir (ya da eksiği: solda "Tanı", merdivende "Yönlendirme"
 * yazan çelişik ekran).
 */

import { describe, expect, test } from "bun:test";

import { resolveCourseAssistantIdentity } from "./course-assistant";
import { openableSessionMode, sessionListNeedsReload } from "./use-chat-session";

const student = resolveCourseAssistantIdentity("student", "student_coach");
if (!student) throw new Error("öğrenci kimliği bekleniyordu");

const STUDENT_QA = {
  mode: "qa",
  audience: "student",
  agent_profile: "student_coach",
} as const;

describe("openableSessionMode — liste satırından oturum açma kapısı", () => {
  test("izinli mod + eşleşen zarf: oturum kendi moduyla açılır", () => {
    expect(openableSessionMode(STUDENT_QA, ["qa", "socratic"], student)).toBe("qa");
  });

  test("sınav oturumu sohbet ekranında AÇILMAZ (uç `exam` kabul etmez)", () => {
    expect(
      openableSessionMode(
        { ...STUDENT_QA, mode: "exam" },
        ["qa", "socratic"],
        student,
      ),
    ).toBeNull();
  });

  test("politika modu kapattıysa eski oturum açılmaz", () => {
    expect(openableSessionMode(STUDENT_QA, ["socratic"], student)).toBeNull();
  });

  test("farklı üyelik profiliyle açılmış oturum mevcut persona ile açılmaz", () => {
    expect(
      openableSessionMode(
        {
          ...STUDENT_QA,
          audience: "instructor",
          agent_profile: "instructor_assistant",
        },
        ["qa"],
        student,
      ),
    ).toBeNull();
  });
});

describe("sessionListNeedsReload — liste yalnız gerçekten değiştiyse tazelenir", () => {
  test("yeni oturum listeye satır ekler: tazele", () => {
    expect(
      sessionListNeedsReload({
        wasNewSession: true,
        answerStage: null,
        listedStage: null,
      }),
    ).toBe(true);
  });

  test("Sokratik kademe ilerledi: aktif satır merdivenle çelişmesin, tazele", () => {
    expect(
      sessionListNeedsReload({
        wasNewSession: false,
        answerStage: "nudge",
        listedStage: "diagnose",
      }),
    ).toBe(true);
  });

  test("aynı kademede ikinci ipucu: istek atılmaz", () => {
    expect(
      sessionListNeedsReload({
        wasNewSession: false,
        answerStage: "nudge",
        listedStage: "nudge",
      }),
    ).toBe(false);
  });

  test("QA oturumunda kademe yok: mevcut oturumda tazeleme yok", () => {
    expect(
      sessionListNeedsReload({
        wasNewSession: false,
        answerStage: null,
        listedStage: null,
      }),
    ).toBe(false);
  });
});
