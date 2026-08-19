/**
 * Persona/politika değişiminde sıfırlama kararı.
 *
 * Karar iki yüzeyde (tam ekran + çekmece) ayrı kopyalar hâlinde yaşıyordu;
 * saf `policyResetDecision` tek kaynak oldu. Çivilenen kural: zarf değişince
 * eski rolün konuşması yeni role TAŞINMAZ, mod politika dışında kaldıysa
 * izinli ilk moda dönülür — zarf aynıyken ise mevcut mod rahat bırakılır.
 */

import { describe, expect, test } from "bun:test";

import { resolveCourseAssistantIdentity } from "./course-assistant";
import { assistantPolicyKey, policyResetDecision } from "./use-assistant-policy";

const student = resolveCourseAssistantIdentity("student", "student_coach");
if (!student) throw new Error("öğrenci kimliği bekleniyordu");

describe("assistantPolicyKey", () => {
  test("zarfın dört bileşenini tek anahtara indirger", () => {
    expect(assistantPolicyKey(student, ["socratic", "qa"], 3)).toBe(
      "student:student_coach:socratic,qa:3",
    );
  });

  test("mod sırası ve ipucu sınırı anahtarı değiştirir", () => {
    expect(assistantPolicyKey(student, ["qa"], 5)).not.toBe(
      assistantPolicyKey(student, ["qa", "socratic"], 5),
    );
    expect(assistantPolicyKey(student, ["qa"], 5)).not.toBe(
      assistantPolicyKey(student, ["qa"], 3),
    );
  });
});

describe("policyResetDecision", () => {
  test("zarf aynı ve mod izinliyken sıfırlamaz", () => {
    expect(
      policyResetDecision({
        mode: "qa",
        allowedModes: ["qa", "socratic"],
        policyChanged: false,
      }),
    ).toEqual({ reset: false });
  });

  test("zarf değişince mod hâlâ izinli olsa da konuşma sıfırlanır", () => {
    expect(
      policyResetDecision({
        mode: "socratic",
        allowedModes: ["qa", "socratic"],
        policyChanged: true,
      }),
    ).toEqual({ reset: true, nextMode: "socratic" });
  });

  test("mod politika dışında kaldıysa izinli ilk moda döner — zarf değişmese bile", () => {
    expect(
      policyResetDecision({
        mode: "socratic",
        allowedModes: ["qa"],
        policyChanged: false,
      }),
    ).toEqual({ reset: true, nextMode: "qa" });
  });

  test("izinli mod hiç kalmadıysa karar null modla döner; null'u çağrı yeri yorumlar", () => {
    expect(
      policyResetDecision({ mode: "qa", allowedModes: [], policyChanged: true }),
    ).toEqual({ reset: true, nextMode: null });
  });

  test("modsuz konuşma (çekmece) izinli ilk moda kurulur", () => {
    expect(
      policyResetDecision({
        mode: null,
        allowedModes: ["socratic", "qa"],
        policyChanged: false,
      }),
    ).toEqual({ reset: true, nextMode: "socratic" });
  });

  test("modsuz konuşma + boş politika: sıfırlanacak bir şey yok", () => {
    expect(
      policyResetDecision({ mode: null, allowedModes: [], policyChanged: false }),
    ).toEqual({ reset: false });
  });
});
