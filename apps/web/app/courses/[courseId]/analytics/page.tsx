"use client";

/**
 * İlerleme ve sınıf analitiği — TASARIM ÖNİZLEMESİ (T038 backend'i, T040 bu ekran).
 *
 * Ekran iki role birden hizmet eder ve rol değişince SORU değişir:
 * - Öğrenci: "hangi konuya çalışmalıyım?" → kendi konu listesi, seviye etiketiyle
 * - Eğitmen: "sınıf nerede zorlanıyor?" → konu bazlı sınıf ortalaması + en çok
 *   yanlış yapılan sorular + kapsam dışı ret oranı
 *
 * Tasarım kararları:
 * - Sıralama en düşük skordan başlar. Listenin tepesi "önce şuna bak" demektir;
 *   alfabetik sıra bu ekranın tek işini yapmasını engellerdi.
 * - Skor sayısı mono, seviye etiketi metinle birlikte. Renk tek başına bilgi
 *   taşımaz (DESIGN.md): "Geliştirilmeli" yazısı rozetin içindedir.
 * - Geliştirilmeli = warning, danger DEĞİL. Kırmızı bu üründe hata rengi değildir
 *   ve düşük skor bir hata değil, çalışma yönüdür.
 * - "Resmî not değildir" ibaresi ekranda zorunludur (ARCHITECTURE §5, KVKK notu).
 */

import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Badge, Card } from "@/components/ui";
import { getStoredUser } from "@/lib/api";

/** Seviye eşikleri spec FR-027 ile birebir: <0.40 · 0.40-0.74 · >=0.75 */
function levelFor(score: number) {
  if (score >= 0.75) return { label: "İyi", tone: "success" as const };
  if (score >= 0.4) return { label: "Orta", tone: "info" as const };
  return { label: "Geliştirilmeli", tone: "warning" as const };
}

interface TopicRow {
  name: string;
  /** 0-1 arası EWMA skoru */
  score: number;
  answers: number;
  /** Eğitmen görünümünde sınıf ortalaması, öğrencide kendi skoru */
  classAverage?: number;
}

const STUDENT_TOPICS: TopicRow[] = [
  { name: "Deadlock", score: 0.32, answers: 6 },
  { name: "Bellek yönetimi", score: 0.48, answers: 4 },
  { name: "CPU zamanlama", score: 0.71, answers: 9 },
  { name: "Senkronizasyon", score: 0.78, answers: 5 },
  { name: "Süreçler ve thread'ler", score: 0.86, answers: 11 },
];

const INSTRUCTOR_TOPICS: TopicRow[] = [
  { name: "Deadlock", score: 0.38, answers: 84, classAverage: 0.38 },
  { name: "Senkronizasyon", score: 0.52, answers: 61, classAverage: 0.52 },
  { name: "Bellek yönetimi", score: 0.63, answers: 73, classAverage: 0.63 },
  { name: "CPU zamanlama", score: 0.74, answers: 96, classAverage: 0.74 },
  { name: "Süreçler ve thread'ler", score: 0.81, answers: 108, classAverage: 0.81 },
];

const MISSED_QUESTIONS = [
  { topic: "Deadlock", stem: "Banker's algoritmasında güvenli durum ne demektir?", wrongRate: 0.68 },
  { topic: "Senkronizasyon", stem: "wait() çağrısı mutex içinde yapılırsa ne olur?", wrongRate: 0.61 },
  { topic: "Bellek yönetimi", stem: "Sayfa hatası (page fault) hangi anda oluşur?", wrongRate: 0.54 },
];

/**
 * Özet metrik kartı: dört sayı tek satırda, etiket sayının ALTINDA.
 * Sayı büyük ve mono; göz önce rakama, sonra etikete gider.
 */
function SummaryCard({ items }: { items: { value: string; label: string }[] }) {
  return (
    <Card className="mb-6">
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        {items.map((item) => (
          <div key={item.label}>
            <p className="font-mono text-2xl text-fg">{item.value}</p>
            <p className="mt-1 text-xs text-fg-muted">{item.label}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

/**
 * Konu satırı: sıra numarası · ad · skor · seviye rozeti · ince ilerleme şeridi.
 * Şerit dekoratif değil; iki konuyu yan yana karşılaştırmayı sayıdan hızlı yapar.
 */
function TopicRowItem({ row, rank }: { row: TopicRow; rank: number }) {
  const level = levelFor(row.score);
  return (
    <li className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-0">
      <span className="w-6 shrink-0 font-mono text-xs text-fg-subtle">#{rank}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-fg">{row.name}</p>
        <div className="mt-1.5 h-1 w-full max-w-[220px] rounded-full bg-border">
          <div
            className="h-1 rounded-full bg-fg-subtle"
            style={{ width: `${Math.round(row.score * 100)}%` }}
          />
        </div>
      </div>
      <span className="shrink-0 text-xs text-fg-subtle">{row.answers} cevap</span>
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
  const isInstructor = getStoredUser()?.role === "instructor";

  const topics = isInstructor ? INSTRUCTOR_TOPICS : STUDENT_TOPICS;
  const sorted = [...topics].sort((a, b) => a.score - b.score);
  const average = topics.reduce((sum, t) => sum + t.score, 0) / topics.length;
  const needsWork = topics.filter((t) => t.score < 0.4).length;
  const totalAnswers = topics.reduce((sum, t) => sum + t.answers, 0);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <div className="mb-6 rounded-lg border border-border bg-brand-subtle px-4 py-2">
        <p className="text-sm text-brand">
          Tasarım önizlemesi: sayılar örnek veridir. İlerleme motoru (EWMA servisi)
          yazıldı ve testli; bu ekranı besleyen analitik uçları E fazında bağlanacak.
        </p>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl text-fg">
          {isInstructor ? "Sınıf analitiği" : "İlerlemem"}
        </h1>
        <p className="prose-tr mt-1 text-sm text-fg-muted">
          {isInstructor
            ? "Konu bazlı sınıf ortalaması, en çok yanlış yapılan sorular ve kapsam dışı ret oranı."
            : "Konu bazlı çalışma göstergen. En düşük skordan başlayarak sıralı."}
        </p>
      </div>

      <SummaryCard
        items={
          isInstructor
            ? [
                { value: average.toFixed(2), label: "Sınıf ortalaması" },
                { value: String(needsWork), label: "Zorlanılan konu" },
                { value: String(totalAnswers), label: "Cevaplanan soru" },
                { value: "%7", label: "Kapsam dışı ret oranı" },
              ]
            : [
                { value: average.toFixed(2), label: "Genel skorun" },
                { value: String(needsWork), label: "Çalışman gereken konu" },
                { value: String(totalAnswers), label: "Cevapladığın soru" },
                { value: String(topics.length), label: "Takip edilen konu" },
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
            <TopicRowItem key={row.name} row={row} rank={index + 1} />
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
