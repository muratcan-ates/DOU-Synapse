/**
 * Kaynak eşlemesinin testi — `bun test lib/`, ek bağımlılık yok.
 *
 * Tek bir iddiası var ama üç ekranı birden tutuyor: `snippet` → `quote`
 * kayarsa sohbet, sınav ve soru havuzu aynı anda alıntı yerine başka bir alanı
 * gösterir ve üçü de çalışıyor görünmeye devam eder. İddia eskiden iki test
 * dosyasında ikizlenmişti; kopyalar ayrı ayrı doğru kaldıkları sürece de kimse
 * hangisinin asıl olduğunu bilmiyordu.
 */

import { describe, expect, test } from "bun:test";
import { toSourceInfo } from "./source";
import type { Citation, SourceRef } from "./types";

describe("toSourceInfo — alanlar eşlenir, içerik biçimlenmez", () => {
  test("SourceRef olduğu gibi karta geçer", () => {
    const ref: SourceRef = {
      chunk_id: "93c8e336",
      file_name: "04-synchronization.pdf",
      location: "Sayfa 3",
      snippet: "Mutex sahiplikli bir kilittir…",
    };
    expect(toSourceInfo(ref)).toEqual({
      fileName: "04-synchronization.pdf",
      location: "Sayfa 3",
      quote: "Mutex sahiplikli bir kilittir…",
    });
  });

  test("Citation da geçer; `claim` karta SIZMAZ", () => {
    // Girdi tipi yapısal olmasa üç çağıran üç ayrı eşleme yazmak zorunda
    // kalırdı. `claim`in gösterilmeme kararının gerekçesi `lib/chat.ts`te.
    const citation: Citation = {
      chunk_id: "ch1",
      claim: "Bağlam değişimi PCB'ye kaydedilir.",
      file_name: "01-processes.pdf",
      location: "Sayfa 3",
      snippet: "Context switch gerçekleşir.",
    };
    expect(toSourceInfo(citation)).toEqual({
      fileName: "01-processes.pdf",
      location: "Sayfa 3",
      quote: "Context switch gerçekleşir.",
    });
  });

  test("konum sunucudan geldiği gibi kalır — arayüz biçimlendirmez", () => {
    // "Slayt 3" sunucuda chunk metadata'sından üretilir (Anayasa I); burada
    // yeniden yazılırsa arayüz ölçmediği bir konum iddia etmiş olur.
    const ref: SourceRef = {
      chunk_id: "ch2",
      file_name: "05-deadlock-demo.pptx",
      location: "Slayt 3",
      snippet: "Dört koşul aynı anda sağlanmalıdır.",
    };
    expect(toSourceInfo(ref).location).toBe("Slayt 3");
  });
});
