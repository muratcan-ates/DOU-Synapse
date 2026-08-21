"use client";

/**
 * Sınav provası — TASARIM ÖNİZLEMESİ (backend'i tasks.md D fazında bağlanacak).
 *
 * DESIGN.md sınav kuralları burada gövde bulur:
 * - Sayaç sağ üstte, nötr; son 60 saniyede --warning'e döner. Yanıp sönme YOK.
 * - Soru metni text-lg; şıklar arasında bol boşluk (yanlış tıklama kaygı üretir).
 * - İlerleme "3/10" biçiminde sayısal; ilerleme çubuğu yok.
 * - Giriş animasyonu yok: sınav ekranı hareketsizdir.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Button } from "@/components/ui";

const PREVIEW_QUESTION = {
  index: 3,
  total: 10,
  prompt:
    "Round Robin zamanlama algoritmasında quantum süresinin çok küçük seçilmesi aşağıdakilerden hangisine yol açar?",
  options: [
    "Bağlam değiştirme maliyetinin toplam işlemci zamanı içindeki payı artar",
    "Uzun süreli prosesler kısa olanları sürekli engeller",
    "Bekleme kuyruğu FIFO yerine LIFO davranışı gösterir",
    "Deadlock olasılığı doğrudan artar",
  ],
};

const EXAM_SECONDS = 12 * 60;

export default function ExamPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [remaining, setRemaining] = useState(EXAM_SECONDS);
  const [selected, setSelected] = useState<number | null>(null);

  // Önizleme sayacı: gerçek sınavda süre sunucudan gelir (mod politikası backend'de).
  useEffect(() => {
    const timer = setInterval(
      () => setRemaining((s) => Math.max(0, s - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const lastMinute = remaining <= 60;

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <div className="mb-6 rounded-lg border border-border bg-brand-subtle px-4 py-2">
        <p className="text-sm text-brand">
          Tasarım önizlemesi: sorular örnek veridir. Sınav motoru geliştirme
          planının D fazında bağlanacak.
        </p>
      </div>

      <div className="mx-auto max-w-2xl">
        {/* Üst şerit: ilerleme + sayaç */}
        <div className="mb-8 flex items-center justify-between text-sm">
          <span className="text-fg-muted">
            Soru{" "}
            <span className="font-medium text-fg">
              {PREVIEW_QUESTION.index}/{PREVIEW_QUESTION.total}
            </span>
          </span>
          <span
            aria-live="polite"
            className={`font-mono tabular-nums ${
              lastMinute ? "font-medium text-warning" : "text-fg-muted"
            }`}
          >
            {minutes}:{String(seconds).padStart(2, "0")}
          </span>
        </div>

        <h1 className="prose-tr text-lg leading-7 font-medium text-fg">
          {PREVIEW_QUESTION.prompt}
        </h1>

        <fieldset className="mt-8 space-y-4">
          <legend className="sr-only">Cevap şıkları</legend>
          {PREVIEW_QUESTION.options.map((option, index) => {
            const active = selected === index;
            return (
              <label
                key={index}
                className={`flex min-h-[44px] cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors ${
                  active
                    ? "border-brand bg-brand-subtle"
                    : "border-border bg-surface hover:border-border-strong"
                }`}
              >
                <input
                  type="radio"
                  name="answer"
                  checked={active}
                  onChange={() => setSelected(index)}
                  className="mt-1 h-4 w-4 accent-[var(--brand)]"
                />
                <span className="prose-tr text-sm leading-6 text-fg">
                  {option}
                </span>
              </label>
            );
          })}
        </fieldset>

        <div className="mt-10 flex items-center justify-between">
          <Button variant="secondary" disabled>
            Önceki
          </Button>
          <Button disabled={selected === null}>Sonraki soru</Button>
        </div>

        <p className="mt-6 text-center text-xs text-fg-subtle">
          Sınav modunda ipucu kapalıdır ve her soruya tek deneme hakkı vardır;
          geri bildirim sınav bitiminde verilir.
        </p>
      </div>
    </AppShell>
  );
}
