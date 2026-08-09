"use client";

/**
 * İlerleme ve sınıf analitiği — TASARIM ÖNİZLEMESİ (T038 backend'i, T040 bu ekran).
 *
 * Ekran iki role birden hizmet eder ve rol değişince SORU değişir:
 * - Öğrenci: "hangi konuya çalışmalıyım?" → kendi konu listesi, seviye etiketiyle
 * - Eğitmen: "sınıf nerede zorlanıyor?" → konu bazlı sınıf ortalaması + en çok
 *   yanlış yapılan sorular + kapsam dışı ret oranı
 *
 * Sıralama en düşük skordan başlar: listenin tepesi "önce şuna bak" demektir.
 * Alfabetik sıra bu ekranın tek işini yapmasını engellerdi.
 */

import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { MetricRow, PageHeader, PreviewBanner } from "@/components/page-state";
import { Badge, Card } from "@/components/ui";
import { masteryLevel, MASTERY_THRESHOLDS } from "@/lib/labels";
import { CLASS_TOPICS, MISSED_QUESTIONS, STUDENT_TOPICS, type PreviewTopic } from "@/lib/preview-data";
import { useSession } from "@/lib/session";

/**
 * Konu satırı: sıra · ad · ince ilerleme şeridi · cevap sayısı · skor · seviye.
 * Şerit dekoratif değil; iki konuyu karşılaştırmayı sayıdan hızlı yapar.
 */
function TopicRow({ row, rank }: { row: PreviewTopic; rank: number }) {
  const level = masteryLevel(row.score);
  const percent = Math.round(row.score * 100);
  return (
    <li className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-0">
      <span className="w-6 shrink-0 font-mono text-xs text-fg-subtle">#{rank}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-fg">{row.name}</p>
        <div
          className="mt-1.5 h-1 w-full max-w-[220px] rounded-full bg-border"
          role="img"
          aria-label={`${row.name}: yüzde ${percent}`}
        >
          <div
            className="h-1 rounded-full bg-fg-subtle"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
      <span className="hidden shrink-0 text-xs text-fg-subtle sm:inline">
        {row.answers} cevap
      </span>
      <span className="w-10 shrink-0 text-right font-mono text-sm text-fg">
        {row.score.toFixed(2)}
      </span>
      <span className="w-32 shrink-0 text-right">
        <Badge tone={level.tone}>{level.label}</Badge>
      </span>
    </li>
  );
}

export default function AnalyticsPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor } = useSession();

  const topics = isInstructor ? CLASS_TOPICS : STUDENT_TOPICS;
  const sorted = [...topics].sort((a, b) => a.score - b.score);
  const average = topics.reduce((sum, t) => sum + t.score, 0) / topics.length;
  const needsWork = topics.filter((t) => t.score < MASTERY_THRESHOLDS.medium).length;
  const totalAnswers = topics.reduce((sum, t) => sum + t.answers, 0);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <PreviewBanner>
        sayılar örnek veridir. İlerleme motoru (EWMA servisi) yazıldı ve testli;
        bu ekranı besleyen analitik uçları E fazında bağlanacak.
      </PreviewBanner>

      <PageHeader
        title={isInstructor ? "Sınıf analitiği" : "İlerlemem"}
        description={
          isInstructor
            ? "Konu bazlı sınıf ortalaması, en çok yanlış yapılan sorular ve kapsam dışı ret oranı."
            : "Konu bazlı çalışma göstergen. En düşük skordan başlayarak sıralı."
        }
      />

      <MetricRow
        items={
          isInstructor
            ? [
                { value: average.toFixed(2), label: "Sınıf ortalaması" },
                { value: needsWork, label: "Zorlanılan konu" },
                { value: totalAnswers, label: "Cevaplanan soru" },
                { value: "%7", label: "Kapsam dışı ret oranı" },
              ]
            : [
                { value: average.toFixed(2), label: "Genel skorun" },
                { value: needsWork, label: "Çalışman gereken konu" },
                { value: totalAnswers, label: "Cevapladığın soru" },
                { value: topics.length, label: "Takip edilen konu" },
              ]
        }
      />

      <Card className="mb-6 p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium text-fg">
            {isInstructor ? "Konu bazlı sınıf durumu" : "Konularım"}
          </h2>
          <span className="text-xs text-fg-subtle">önce zorlanılan konu</span>
        </div>
        <ul>
          {sorted.map((row, index) => (
            <TopicRow key={row.name} row={row} rank={index + 1} />
          ))}
        </ul>
      </Card>

      {isInstructor && (
        <Card className="mb-6 p-0">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-medium text-fg">
              En çok yanlış yapılan sorular
            </h2>
          </div>
          <ul>
            {MISSED_QUESTIONS.map((q) => (
              <li
                key={q.stem}
                className="flex items-start gap-4 border-b border-border px-4 py-3 last:border-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="prose-tr text-sm text-fg">{q.stem}</p>
                  <p className="mt-1 text-xs text-fg-subtle">{q.topic}</p>
                </div>
                <span className="shrink-0 font-mono text-sm text-fg">
                  %{Math.round(q.wrongRate * 100)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* ARCHITECTURE §5: bu ibare ekranda zorunludur, dipnot değil. */}
      <p className="prose-tr text-xs text-fg-muted">
        Bu gösterge resmî bir not değildir; nereye çalışılacağını gösteren bir
        çalışma önerisidir. Skor, konu bazlı ağırlıklı ortalamayla hesaplanır ve
        alınan ipucu kademesi cevabın katkısını düşürür.
      </p>
    </AppShell>
  );
}
