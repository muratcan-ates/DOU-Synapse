"use client";

/**
 * Sınav provası — TASARIM ÖNİZLEMESİ (backend'i tasks.md D fazında bağlanacak).
 *
 * DESIGN.md sınav kuralları burada gövde bulur:
 * - Sayaç sağ üstte, nötr; son 60 saniyede --warning'e döner. Yanıp sönme YOK.
 * - Soru metni text-lg; şıklar arasında bol boşluk (yanlış tıklama kaygı üretir).
 * - İlerleme "3/10" biçiminde sayısal; ilerleme çubuğu yok.
 * - Giriş animasyonu yok: sınav ekranı hareketsizdir.
 *
 * Önizlemede ileri-geri gezinme YEREL çalışır. Etkin görünüp hiçbir şey
 * yapmayan buton çalışmayan bir ürün izlenimi verir; akış oynatılabilir, ama
 * cevaplar kaydedilmez ve süre sunucudan gelmez.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { PreviewBanner } from "@/components/page-state";
import { Button } from "@/components/ui";

const PREVIEW_QUESTIONS = [
  {
    prompt:
      "Round Robin zamanlama algoritmasında quantum süresinin çok küçük seçilmesi aşağıdakilerden hangisine yol açar?",
    options: [
      "Bağlam değiştirme maliyetinin toplam işlemci zamanı içindeki payı artar",
      "Uzun süreli prosesler kısa olanları sürekli engeller",
      "Bekleme kuyruğu FIFO yerine LIFO davranışı gösterir",
      "Deadlock olasılığı doğrudan artar",
    ],
  },
  {
    prompt:
      "Deadlock oluşabilmesi için aşağıdaki koşullardan hangisinin sağlanması gerekli değildir?",
    options: [
      "Karşılıklı dışlama (mutual exclusion)",
      "Tut ve bekle (hold and wait)",
      "Önceliklendirme (priority scheduling)",
      "Döngüsel bekleme (circular wait)",
    ],
  },
  {
    prompt:
      "Sayfalama kullanan bir sistemde sayfa hatası (page fault) hangi anda oluşur?",
    options: [
      "İstenen sayfa fiziksel bellekte bulunmadığında",
      "Sayfa tablosu tamamen dolduğunda",
      "Proses kendi adres uzayının dışına yazmaya çalıştığında",
      "Bağlam değiştirme sırasında her zaman",
    ],
  },
];

const TOTAL_QUESTIONS = 10;
const EXAM_SECONDS = 12 * 60;

export default function ExamPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [remaining, setRemaining] = useState(EXAM_SECONDS);
  const [index, setIndex] = useState(0);
  // Soru başına seçim: geri dönüldüğünde önceki cevap yerinde durmalı.
  const [answers, setAnswers] = useState<Record<number, number>>({});

  // Önizleme sayacı: gerçek sınavda kalan süre sunucudan gelir; istemci
  // saatine güvenilmez (mod politikaları backend'de).
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

  const question = PREVIEW_QUESTIONS[index % PREVIEW_QUESTIONS.length];
  const selected = answers[index] ?? null;
  const isLast = index === TOTAL_QUESTIONS - 1;

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <PreviewBanner>
        sorular örnek veridir ve cevaplar kaydedilmez. Sınav motoru geliştirme
        planının D fazında bağlanacak.
      </PreviewBanner>

      <div className="mx-auto max-w-2xl">
        {/* Üst şerit: ilerleme + sayaç */}
        <div className="mb-8 flex items-center justify-between text-sm">
          <span className="text-fg-muted">
            Soru{" "}
            <span className="font-medium text-fg">
              {index + 1}/{TOTAL_QUESTIONS}
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
          {question.prompt}
        </h1>

        <fieldset className="mt-8 space-y-4">
          <legend className="sr-only">Cevap şıkları</legend>
          {question.options.map((option, optionIndex) => {
            const active = selected === optionIndex;
            return (
              <label
                key={option}
                className={`flex min-h-[44px] cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors ${
                  active
                    ? "border-brand bg-brand-subtle"
                    : "border-border bg-surface hover:border-border-strong"
                }`}
              >
                <input
                  type="radio"
                  name={`answer-${index}`}
                  checked={active}
                  onChange={() =>
                    setAnswers((prev) => ({ ...prev, [index]: optionIndex }))
                  }
                  className="mt-1 h-4 w-4 accent-[var(--brand)]"
                />
                <span className="prose-tr text-sm leading-6 text-fg">{option}</span>
              </label>
            );
          })}
        </fieldset>

        <div className="mt-10 flex items-center justify-between">
          <Button
            variant="secondary"
            disabled={index === 0}
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
          >
            Önceki
          </Button>
          <Button
            disabled={selected === null || isLast}
            onClick={() => setIndex((i) => Math.min(TOTAL_QUESTIONS - 1, i + 1))}
          >
            {isLast ? "Son soru" : "Sonraki soru"}
          </Button>
        </div>

        <p className="mt-6 text-center text-xs text-fg-subtle">
          Sınav modunda ipucu kapalıdır ve her soruya tek deneme hakkı vardır;
          geri bildirim sınav bitiminde verilir.
        </p>
      </div>
    </AppShell>
  );
}
