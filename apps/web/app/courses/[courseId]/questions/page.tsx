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
 * değişir, klavyeyle yukarı-aşağı ilerlenebilir.
 *
 * Neden kaynak parçası detayın içinde:
 * Onay kararı "bu soru materyalde gerçekten var mı" sorusudur. Kaynak, cevap
 * anahtarıyla eşit ağırlıkta gösterilir; eğitmen sekme değiştirmek zorunda kalırsa
 * kaynağa bakmadan onaylamaya başlar.
 */

import { useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Badge, Button, Card } from "@/components/ui";
import { SourceCard, type SourceInfo } from "@/components/source-card";

type QuestionType = "mcq" | "open" | "code_trace" | "bug_hunt";
type QuestionStatus = "draft" | "approved" | "rejected";

const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Çoktan seçmeli",
  open: "Açık uçlu",
  code_trace: "Kod çıktısı",
  bug_hunt: "Hata bulma",
};

/**
 * Durum rozetleri. Reddedilen soru "neutral" — danger DEĞİL: red bir hata değil,
 * eğitmenin kararıdır ve kırmızı bu üründe hata rengi olarak kullanılmaz.
 */
const STATUS: Record<QuestionStatus, { label: string; tone: "success" | "info" | "neutral" }> = {
  draft: { label: "Taslak", tone: "info" },
  approved: { label: "Onaylandı", tone: "success" },
  rejected: { label: "Reddedildi", tone: "neutral" },
};

interface DraftQuestion {
  id: string;
  topic: string;
  type: QuestionType;
  status: QuestionStatus;
  stem: string;
  options?: string[];
  answerKey: string;
  source: SourceInfo;
}

const QUESTIONS: DraftQuestion[] = [
  {
    id: "S-001",
    topic: "Deadlock",
    type: "mcq",
    status: "draft",
    // Olumsuz soru kökü: vurgu için büyük harf kullanılmaz (DESIGN.md, i/İ kuralı).
    stem: "Deadlock oluşabilmesi için aşağıdaki koşullardan hangisinin sağlanması gerekli değildir?",
    options: [
      "Karşılıklı dışlama (mutual exclusion)",
      "Tut ve bekle (hold and wait)",
      "Önceliklendirme (priority scheduling)",
      "Döngüsel bekleme (circular wait)",
    ],
    answerKey: "Önceliklendirme (priority scheduling)",
    source: {
      fileName: "05-deadlock-demo.pdf",
      location: "Sayfa 1",
      quote:
        "Deadlock için dört Coffman koşulunun aynı anda sağlanması gerekir: karşılıklı dışlama, tut ve bekle, kesintiye uğratamama, döngüsel bekleme.",
    },
  },
  {
    id: "S-002",
    topic: "Senkronizasyon",
    type: "bug_hunt",
    status: "draft",
    stem: "Aşağıdaki üretici-tüketici kodunda wait(empty) çağrısı mutex kritik bölgesinin içinde yapılıyor. Bu sıralama hatasının doğrulanmış sonucu nedir?",
    answerKey:
      "Kilitlenme (deadlock). Tampon doluyken üretici mutex'i tutarken wait(empty)'de bloke olur, tüketici mutex'i alamadığı için tamponu boşaltamaz.",
    source: {
      fileName: "04-synchronization.pdf",
      location: "Sayfa 3",
      quote:
        "Sinyal semaforu beklemesi mutex kilitliyken yapılırsa, tampon doluyken bekleyen üretici mutex'i tutar durumda kilitlenmiş kalabilir.",
    },
  },
  {
    id: "S-003",
    topic: "CPU zamanlama",
    type: "open",
    status: "approved",
    stem: "Round Robin zamanlamada quantum süresinin çok küçük seçilmesinin sistem başarımına etkisini açıklayınız.",
    answerKey:
      "Quantum küçüldükçe bağlam değiştirme sayısı artar; bağlam değiştirme maliyetinin toplam işlemci zamanı içindeki payı büyür ve yararlı iş için kalan süre azalır.",
    source: {
      fileName: "02-cpu-scheduling.pdf",
      location: "Sayfa 2",
      quote:
        "Quantum çok küçük seçilirse bağlam değiştirme maliyeti toplam işlemci zamanının kayda değer bir bölümünü tüketir.",
    },
  },
  {
    id: "S-004",
    topic: "Bellek yönetimi",
    type: "code_trace",
    status: "draft",
    stem: "Verilen sayfalama örneğinde 4 KB sayfa boyutu ve 12 bitlik ofset ile 0x1A2B mantıksal adresinin sayfa numarası kaçtır?",
    answerKey: "Sayfa numarası 1, ofset 0xA2B.",
    source: {
      fileName: "03-memory-management.pdf",
      location: "Sayfa 2",
      quote:
        "4 KB sayfa boyutunda ofset alanı 12 bittir; kalan üst bitler sayfa numarasını verir.",
    },
  },
  {
    id: "S-005",
    topic: "Süreçler",
    type: "mcq",
    status: "rejected",
    stem: "fork() çağrısı başarısız olduğunda ebeveyn sürece hangi değeri döndürür?",
    options: ["0", "-1", "Çocuğun PID'i", "Tanımsız"],
    answerKey: "-1",
    source: {
      fileName: "01-processes.pdf",
      location: "Sayfa 2",
      quote:
        "fork() başarısızlıkta ebeveyne -1 döndürür ve yeni süreç yaratılmaz.",
    },
  },
];

export default function QuestionsPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [selectedId, setSelectedId] = useState(QUESTIONS[0].id);
  const selected = QUESTIONS.find((q) => q.id === selectedId) ?? QUESTIONS[0];

  const drafts = QUESTIONS.filter((q) => q.status === "draft").length;
  const approved = QUESTIONS.filter((q) => q.status === "approved").length;

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <div className="mb-6 rounded-lg border border-border bg-brand-subtle px-4 py-2">
        <p className="text-sm text-brand">
          Tasarım önizlemesi: sorular örnek veridir. Soru üretici ve onay uçları
          geliştirme planının D fazında bağlanacak.
        </p>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl text-fg">Soru havuzu</h1>
        <p className="prose-tr mt-1 text-sm text-fg-muted">
          Sistem soruları ders materyalinden üretir ve taslak olarak buraya
          düşürür. Onaylamadığınız hiçbir soru öğrenciye görünmez.
        </p>
      </div>

      <Card className="mb-6">
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          <div>
            <p className="font-mono text-2xl text-fg">{drafts}</p>
            <p className="mt-1 text-xs text-fg-muted">Onay bekleyen</p>
          </div>
          <div>
            <p className="font-mono text-2xl text-fg">{approved}</p>
            <p className="mt-1 text-xs text-fg-muted">Öğrenciye açık</p>
          </div>
          <div>
            <p className="font-mono text-2xl text-fg">{QUESTIONS.length}</p>
            <p className="mt-1 text-xs text-fg-muted">Toplam soru</p>
          </div>
          <div>
            <p className="font-mono text-2xl text-fg">4</p>
            <p className="mt-1 text-xs text-fg-muted">Kaynak materyal</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* Sol: sıra korunan liste. Seçili satır kırmızı sol şeritle işaretli —
            kırmızının meşru kullanımlarından biri (aktif gösterge). */}
        <Card className="h-fit p-0">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-medium text-fg">Üretilen sorular</h2>
          </div>
          <ul>
            {QUESTIONS.map((q) => {
              const active = q.id === selectedId;
              return (
                <li key={q.id}>
                  <button
                    onClick={() => setSelectedId(q.id)}
                    aria-current={active ? "true" : undefined}
                    className={`w-full border-b border-l-2 border-border px-4 py-3 text-left transition-colors last:border-b-0 ${
                      active
                        ? "border-l-brand bg-brand-subtle/40"
                        : "border-l-transparent hover:bg-brand-subtle/20"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-fg-subtle">{q.id}</span>
                      <Badge tone={STATUS[q.status].tone}>{STATUS[q.status].label}</Badge>
                    </div>
                    <p className="prose-tr mt-1.5 line-clamp-2 text-sm text-fg">
                      {q.stem}
                    </p>
                    <p className="mt-1 text-xs text-fg-subtle">
                      {q.topic} · {TYPE_LABEL[q.type]}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>

        {/* Sağ: karar için gereken her şey tek ekranda — soru, cevap anahtarı, kaynak. */}
        <Card>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{TYPE_LABEL[selected.type]}</Badge>
            <Badge tone={STATUS[selected.status].tone}>
              {STATUS[selected.status].label}
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
                    <span className="mt-0.5 shrink-0 text-xs text-fg-subtle">
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
            <Button variant="primary" disabled={selected.status === "approved"}>
              Onayla ve öğrenciye aç
            </Button>
            <Button variant="secondary" disabled={selected.status === "rejected"}>
              Reddet
            </Button>
            <p className="text-xs text-fg-subtle">
              Onaylanmayan soru öğrenci akışında hiç görünmez.
            </p>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
