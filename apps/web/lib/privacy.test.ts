import { describe, expect, spyOn, test } from "bun:test";
import {
  chatDeletionMessage,
  downloadDataExport,
  exportFilename,
  type UserDataExport,
} from "./privacy";

describe("kişisel veri dışa aktarma", () => {
  test("tarih dosya adına kararlı biçimde girer", () => {
    expect(exportFilename("2026-08-10T01:15:00+03:00")).toBe(
      "dou-synapse-verilerim-2026-08-10.json",
    );
  });

  test("bozuk tarihte güvenli dosya adı üretir", () => {
    expect(exportFilename("beklenmeyen")).toBe("dou-synapse-verilerim-veri.json");
  });
});

describe("sohbet silme sonucu", () => {
  test("boş ve dolu sonuç birbirinden ayrılır", () => {
    expect(chatDeletionMessage(0)).toBe("Silinecek sohbet geçmişi bulunamadı.");
    expect(chatDeletionMessage(3)).toBe("3 sohbet oturumu uygulama veritabanından silindi.");
  });
});


describe("v2 dışa aktarma sözleşmesi", () => {
  test("indirilen JSON sürümü, kullanıcı verisini ve kapsam açıklamasını korur", async () => {
    const payload = {
      schema_version: "2",
      generated_at: "2026-09-08T10:00:00+03:00",
      profile: {
        id: "export-test-user",
        email: "export-test@example.invalid",
        full_name: "Test Öğrencisi",
        created_at: "2026-09-01T10:00:00+03:00",
      },
      memberships: [{ course_id: "course-test", role: "student" }],
      chat_sessions: [{ id: "chat-test", messages: [{ content: "Örnek soru" }] }],
      exam_sessions: [{ id: "exam-test", answers: [{ given: "Örnek yanıt" }] }],
      mastery: [{ topic_id: "topic-test", score: 0.5 }],
      not_included: ["Kota ve güvenlik operasyon kayıtları dahil değildir."],
    } satisfies UserDataExport;
    const documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, "document");
    const blobs: Blob[] = [];
    const link = { href: "", download: "", click() {} };
    const click = spyOn(link, "click");
    const createUrl = spyOn(URL, "createObjectURL").mockImplementation((value) => {
      expect(value).toBeInstanceOf(Blob);
      blobs.push(value as Blob);
      return "blob:privacy-export-test";
    });
    const revokeUrl = spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: {
        createElement(tag: string) {
          expect(tag).toBe("a");
          return link;
        },
      },
    });
    try {
      downloadDataExport(payload);
      expect(blobs).toHaveLength(1);
      expect(blobs[0].type).toBe("application/json;charset=utf-8");
      expect(JSON.parse(await blobs[0].text())).toEqual(payload);
      expect(link.download).toBe("dou-synapse-verilerim-2026-09-08.json");
      expect(link.href).toBe("blob:privacy-export-test");
      expect(click).toHaveBeenCalledTimes(1);
      expect(revokeUrl).toHaveBeenCalledWith("blob:privacy-export-test");
    } finally {
      createUrl.mockRestore();
      revokeUrl.mockRestore();
      click.mockRestore();
      if (documentDescriptor) Object.defineProperty(globalThis, "document", documentDescriptor);
      else Reflect.deleteProperty(globalThis, "document");
    }
  });
});
