"use client";

/**
 * Soru havuzu ve eğitmen onayı — TASARIM ÖNİZLEMESİ (T029 üretici, T030 uçları).
 *
 * Ürünün en kritik yetki ekranı: yapay zekâ soruyu üretir, EĞİTMEN yayınlar.
 * Danışman toplantısının ana isteği buydu — çerçeveyi eğitmen kurar, sistem
 * doldurur, onaysız hiçbir soru öğrenciye görünmez.
 *
 * Neden liste + detay (modal değil):
 * Eğitmen otuz taslağı arka arkaya elden geçirecek. Modal her soruda açılıp
 * kapanır ve sırayı kaybettirir; sol listede sıra korunur, sağda yalnız içerik
 * değişir.
 *
 * Neden kaynak parçası detayın içinde:
 * Onay kararı "bu soru materyalde gerçekten var mı" sorusudur. Kaynak, cevap
 * anahtarıyla eşit ağırlıkta gösterilir; eğitmen sekme değiştirmek zorunda
 * kalırsa kaynağa bakmadan onaylamaya başlar.
 *
 * Önizlemede onay/red YEREL çalışır: karar sunucuya gitmez ama ekranda
 * gerçekleşir. Etkin görünüp hiçbir şey yapmayan buton, çalışmayan bir ürün
 * izlenimi verir; bu yüzden akış oynatılabilir, sonucun kalıcı olmadığı ise
 * kararın yanında yazılıdır.
 */

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { MetricRow, PageHeader, PreviewBanner } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Badge, Button, Card } from "@/components/ui";
import { QUESTION_STATUS, QUESTION_TYPE, type QuestionStatus } from "@/lib/labels";
import { PREVIEW_QUESTIONS } from "@/lib/preview-data";

export default function QuestionsPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();

  // Önizleme kararları burada tutulur; sayfadan çıkınca sıfırlanır.
  const [decisions, setDecisions] = useState<Record<string, QuestionStatus>>({});
  const [selectedId, setSelectedId] = useState(PREVIEW_QUESTIONS[0].id);

  const questions = useMemo(
    () =>
      PREVIEW_QUESTIONS.map((q) => ({ ...q, status: decisions[q.id] ?? q.status })),
    [decisions],
  );

  const selected = questions.find((q) => q.id === selectedId) ?? questions[0];
  const drafts = questions.filter((q) => q.status === "draft").length;
  const approved = questions.filter((q) => q.status === "approved").length;

  function decide(id: string, status: QuestionStatus) {
    setDecisions((prev) => ({ ...prev, [id]: status }));
    // Karardan sonra sıradaki taslağa geç: eğitmen otuz soruyu elden
    // geçirirken her seferinde listeye dönmek zorunda kalmamalı.
    const next = questions.find((q) => q.id !== id && q.status === "draft");
    if (next) setSelectedId(next.id);
  }

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <PreviewBanner>
        sorular örnek veridir ve onay kararı kaydedilmez. Soru üretici ile onay
        uçları geliştirme planının D fazında bağlanacak.
      </PreviewBanner>

      <PageHeader
        title="Soru havuzu"
        description="Sistem soruları ders materyalinden üretir ve taslak olarak buraya düşürür. Onaylamadığınız hiçbir soru öğrenciye görünmez."
      />

      <MetricRow
        items={[
          { value: drafts, label: "Onay bekleyen" },
          { value: approved, label: "Öğrenciye açık" },
          { value: questions.length, label: "Toplam soru" },
          { value: 4, label: "Kaynak materyal" },
        ]}
      />

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Card className="h-fit p-0">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-medium text-fg">Üretilen sorular</h2>
          </div>
          <ul>
            {questions.map((q) => {
              const active = q.id === selected.id;
              const status = QUESTION_STATUS[q.status];
              return (
                <li key={q.id}>
                  {/* Seçili satır kırmızı sol şeritle işaretli — kırmızının
                      meşru kullanımlarından biri (aktif gösterge). */}
                  <button
                    onClick={() => setSelectedId(q.id)}
                    aria-current={active ? "true" : undefined}
                    className={`w-full border-b border-l-2 border-border px-4 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                      active
                        ? "border-l-brand bg-brand-subtle/40"
                        : "border-l-transparent hover:bg-brand-subtle/20"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-fg-subtle">{q.id}</span>
                      <Badge tone={status.tone}>{status.label}</Badge>
                    </div>
                    <p className="prose-tr mt-1.5 line-clamp-2 text-sm text-fg">
                      {q.stem}
                    </p>
                    <p className="mt-1 text-xs text-fg-subtle">
                      {q.topic} · {QUESTION_TYPE[q.type]}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{QUESTION_TYPE[selected.type]}</Badge>
            <Badge tone={QUESTION_STATUS[selected.status].tone}>
              {QUESTION_STATUS[selected.status].label}
            </Badge>
            <span className="text-xs text-fg-subtle">
              {selected.id} · {selected.topic}
            </span>
          </div>

          <p className="prose-tr text-lg text-fg">{selected.stem}</p>

          {selected.options && (
            <ul className="mt-5 space-y-2">
              {selected.options.map((option) => {
                const correct = option === selected.answerKey;
                return (
                  <li
                    key={option}
                    className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${
                      correct
                        ? "border-success bg-success-bg text-fg"
                        : "border-border text-fg-muted"
                    }`}
                  >
                    <span className="mt-0.5 w-10 shrink-0 text-xs text-fg-subtle">
                      {correct ? "doğru" : ""}
                    </span>
                    <span className="prose-tr">{option}</span>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-6">
            <h3 className="mb-2 text-xs font-medium text-fg-muted">Cevap anahtarı</h3>
            <p className="prose-tr rounded-lg border border-border bg-bg px-4 py-3 text-sm text-fg">
              {selected.answerKey}
            </p>
          </div>

          <div className="mt-6">
            <h3 className="mb-2 text-xs font-medium text-fg-muted">
              Üretimde kullanılan kaynak
            </h3>
            <SourceCard source={selected.source} />
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
            <Button
              variant="primary"
              disabled={selected.status === "approved"}
              onClick={() => decide(selected.id, "approved")}
            >
              {selected.status === "approved" ? "Onaylandı" : "Onayla ve öğrenciye aç"}
            </Button>
            <Button
              variant="secondary"
              disabled={selected.status === "rejected"}
              onClick={() => decide(selected.id, "rejected")}
            >
              {selected.status === "rejected" ? "Reddedildi" : "Reddet"}
            </Button>
            <p className="text-xs text-fg-subtle">
              Onaylanmayan soru öğrenci akışında hiç görünmez. Önizlemede karar
              kaydedilmez.
            </p>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
