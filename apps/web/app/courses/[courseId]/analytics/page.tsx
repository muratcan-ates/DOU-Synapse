"use client";

/**
 * İlerleme ve sınıf analitiği — T040, gerçek uçlara bağlı.
 *
 * API: `GET /courses/{id}/analytics/me` (öğrenci) · `.../analytics/class` (eğitmen)
 *
 * Ekran iki role birden hizmet eder ve rol değişince SORU değişir:
 * - Öğrenci: "hangi konuya çalışmalıyım?" → kendi konu listesi, seviye etiketiyle
 * - Eğitmen: "sınıf nerede zorlanıyor?" → konu bazlı sınıf ortalaması + soru
 *   bazlı yanlış oranı + kapsam dışı ret oranı
 *
 * Ekranın asıl işi sayı çizmek değil, ölçülmemiş olanı ölçülmüş gibi
 * göstermemektir (Anayasa III). Üç yerde bilinçli olarak boşluk bırakılır:
 * çalışılmamış konu listeye 0,00 ile girmez, null ortalama 0 gibi yazılmaz,
 * hesaplanamamış oranın yerine sunucunun Türkçe açıklaması konur. Biçimlendirme
 * kuralları `lib/analytics.ts`'te ve testlidir; buradaki dosya yalnız çizer.
 *
 * Sıralama sunucudan gelir (en düşük skordan): listenin tepesi "önce şuna bak"
 * demektir. İstemcide yeniden sıralanmaz — iki sıralama kuralı er geç ayrışır.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState } from "@/components/ui";
import {
  barPercent,
  isClassAnalytics,
  MASTERY_LEVEL,
  missedRateText,
  OUT_OF_SCOPE_SOURCE,
  outOfScopeCountsText,
  rateText,
  scoreText,
  topicRows,
  untrackedNote,
  volumeText,
  type TopicRow,
} from "@/lib/analytics";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ClassAnalytics, StudentAnalytics } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function AnalyticsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  /*
   * `ready` gelmeden rol dalına GİRİLMEZ (Anayasa IV, fail-closed): rol
   * localStorage'dan ilk efektte okunur ve o ana kadar "eğitmen değil"
   * varsayımı geçerlidir. Kapı yalnız görünümü değil İSTEĞİ de tutuyor —
   * `useResource` mount olur olmaz çağrı yapar, dolayısıyla veri çeken kısım
   * ayrı bir bileşende ve ancak rol bilindiğinde mount ediliyor. Aksi hâlde
   * eğitmen için önce `/me` çağrılır, sonra `/class` ile ikinci kez çekilirdi.
   *
   * Rol yalnız ARAYÜZÜ şekillendirir; yetki sunucuda doğrulanır (Anayasa II):
   * `/analytics/class` zaten `CourseInstructorDep`'ten geçer.
   */
  const { isInstructor, ready } = useSession(courseId);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <InstructorGate ready={ready} isInstructor={isInstructor}>
        {(instructor) => <AnalyticsView courseId={courseId} isInstructor={instructor} />}
      </InstructorGate>
    </AppShell>
  );
}

function AnalyticsView({
  courseId,
  isInstructor,
}: {
  courseId: string;
  isInstructor: boolean;
}) {
  const fetchAnalytics = useCallback(
    () =>
      isInstructor
        ? api.get<ClassAnalytics>(`/courses/${courseId}/analytics/class`)
        : api.get<StudentAnalytics>(`/courses/${courseId}/analytics/me`),
    [courseId, isInstructor],
  );

  /*
   * Polling YOK: bu ekranın verisi kullanıcı başka bir ekranda soru cevaplayınca
   * değişir, kendiliğinden değil. Durdurulmayan bir tazeleme döngüsü gereksiz iş
   * olurdu (Anayasa XI). Elle tazeleme başlıktaki düğmededir ve gerçekten çalışır.
   */
  const {
    data,
    error,
    refreshError,
    errorKind,
    errorRequestId,
    loading,
    reload,
  } = useResource<StudentAnalytics | ClassAnalytics>(fetchAnalytics, [
    courseId,
    isInstructor,
  ]);

  return (
    <>
      <PageHeader
        title={isInstructor ? "Sınıf analitiği" : "İlerlemem"}
        description={
          isInstructor
            ? "Konu bazlı sınıf ortalaması, soru bazlı yanlış oranı ve kapsam dışı ret oranı."
            : "Konu bazlı çalışma göstergen. En düşük skordan başlayarak sıralı."
        }
        action={
          <Button variant="secondary" onClick={() => void reload()}>
            Yenile
          </Button>
        }
      />

      <ScoreDisclaimer />

      {/* Elde veri varken tazeleme hatası sayfayı SİLMEZ; satır içinde durur. */}
      {refreshError && (
        <div className="mb-6">
          <ErrorNote
            message={refreshError}
            kind={errorKind}
            requestId={errorRequestId}
            onRetry={() => void reload()}
          />
        </div>
      )}

      {error && (
        <ErrorNote
          message={error}
          kind={errorKind}
          requestId={errorRequestId}
          onRetry={() => void reload()}
        />
      )}
      {loading && <Loading />}

      {data && (
        <>
          <Summary data={data} />
          <UntrackedNote count={data.untracked_topics} />
          <TopicList
            courseId={courseId}
            rows={topicRows(data)}
            isInstructor={isInstructor}
          />
          {isClassAnalytics(data) && (
            <>
              <OutOfScopeCard stat={data.out_of_scope} />
              <MissedQuestions questions={data.missed_questions} />
            </>
          )}
        </>
      )}
    </>
  );
}

/**
 * "Resmî not değildir" ibaresi — spec gereği ZORUNLU (ARCHITECTURE §5).
 *
 * Sayfanın dibinde bir dipnot değil, sayıların ÜSTÜNDE duruyor: bu ekranı açan
 * kişi rakamları okumadan önce neye baktığını bilmeli. Veri gelmese de, hata
 * olsa da yerinde kalır — ibarenin görünürlüğü isteğin başarısına bağlı değil.
 * Ton nötr: bu bir uyarı değil, ölçünün tanımı.
 */
function ScoreDisclaimer() {
  return (
    <Card variant="soft" className="mb-6">
      <p className="prose-tr text-sm text-fg-muted">
        <span className="font-medium text-fg">Bu gösterge resmî bir not değildir.</span>{" "}
        Nereye çalışılacağını gösteren pedagojik bir öneridir. Skor, son cevaplara
        daha çok ağırlık veren üstel bir ortalamayla hesaplanır ve alınan ipucu
        kademesi cevabın katkısını düşürür.
      </p>
    </Card>
  );
}

/**
 * Özet metrikler.
 *
 * `average_score` null olabilir ve o zaman "Ölçüm yok" yazar — 0 değil.
 * Sunucunun göndermediği hiçbir sayı burada türetilmez: "zorlanılan konu"
 * `needs_work_topics`'ten, "cevaplanan soru" `answered_questions`'tan gelir;
 * ikisi de istemcide yeniden sayılmaz.
 */
function Summary({ data }: { data: StudentAnalytics | ClassAnalytics }) {
  if (isClassAnalytics(data)) {
    return (
      <MetricRow
        items={[
          { value: scoreText(data.average_score), label: "Sınıf ortalaması" },
          { value: data.tracked_topics, label: "Ölçülen konu" },
          { value: data.answered_questions, label: "Cevaplanan soru" },
          { value: data.student_count, label: "Ölçüme giren öğrenci" },
        ]}
      />
    );
  }
  return (
    <MetricRow
      items={[
        { value: scoreText(data.average_score), label: "Genel skorun" },
        { value: data.needs_work_topics, label: "Çalışman gereken konu" },
        { value: data.answered_questions, label: "Cevapladığın soru" },
        { value: data.tracked_topics, label: "Ölçülen konu" },
      ]}
    />
  );
}

/** "N konu henüz çalışılmadı" — sıfır puanla değil, sayıyla söylenir. */
function UntrackedNote({ count }: { count: number }) {
  const note = untrackedNote(count);
  if (!note) return null;
  return <p className="prose-tr mb-6 text-sm text-fg-muted">{note}</p>;
}

/**
 * Konu satırı — iki katman: üstte sıra · ad · skor, altta şerit · hacim · seviye.
 *
 * Tek satıra dizilmiyordu ve telefonda satırın en önemli bilgisi kayboluyordu:
 * sabit genişlikli sütunlar (sıra 24px + skor 48px + rozet 128px + boşluklar
 * 64px = 264px) 293px'lik iç genişliğin neredeyse tamamını yiyordu ve
 * `min-w-0 flex-1` olan konu adına 29px kalıyordu — "Deadlock" ekranda "D."
 * olarak çiziliyordu. DESIGN.md öğrenci ekranlarını önce mobil için tasarlar;
 * "hangi konuya çalışmalıyım?" sorusunun cevabı okunamıyorsa ekran çalışmıyor
 * demektir. Rozet ve hacim ikinci satıra indi, ad tam genişliği aldı.
 *
 * Şerit `aria-hidden`: taşıdığı bilgi satırın kendisinde zaten yazılı (konu adı,
 * skor, seviye rozeti). `role="img"` + aria-label o metni birebir tekrarlardı ve
 * ekran okuyucu her satırı iki kez okurdu. Şerit görsel karşılaştırmayı
 * hızlandırır, bilgi eklemez.
 *
 * Dolgu `--fg-subtle` (nötr): DESIGN.md §Known Gaps kategorik analitik paletini
 * henüz karara bağlamadı; renk bilgi taşımadığı için seviye rozetten okunur.
 */
function TopicRowItem({ row, rank }: { row: TopicRow; rank: number }) {
  const level = MASTERY_LEVEL[row.level];
  return (
    <li className="border-b border-border px-4 py-3 last:border-0">
      <div className="flex items-center gap-3">
        <span className="w-6 shrink-0 text-xs tabular-nums text-fg-subtle">#{rank}</span>
        <p className="min-w-0 flex-1 truncate text-sm text-fg">{row.name}</p>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-fg">
          {scoreText(row.score)}
        </span>
      </div>
      {/* pl-9 = sıra sütunu (24px) + boşluk (12px): alt katman adla hizalanır. */}
      <div className="mt-1.5 flex items-center gap-3 pl-9">
        <div
          aria-hidden="true"
          className="h-1.5 w-full max-w-[26rem] rounded-full bg-surface-sunken"
        >
          <div
            className="h-1.5 rounded-full bg-fg-subtle transition-[width] duration-500"
            style={{ width: `${barPercent(row.score)}%` }}
          />
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-3">
          {/*
            Hacim dar ekranda `hidden` ile gizlenmiyor: `display:none`
            erişilebilirlik ağacından da düşürür ve telefonda ekran okuyucu
            kullanan öğrenci skorun kaç cevaba dayandığını hiç öğrenemez.
            `sr-only` görsel olarak gizler, okunur bırakır.
          */}
          <span className="sr-only text-xs text-fg-subtle sm:not-sr-only">
            {volumeText(row)}
          </span>
          <Badge tone={level.tone}>{level.label}</Badge>
        </div>
      </div>
    </li>
  );
}

/**
 * Konu listesi. Boşluk bir hata değildir: henüz ölçüm yok demektir, bu yüzden
 * kırmızı, ünlem veya uyarı üçgeni yok — sakin bir sonraki adım var.
 */
function TopicList({
  courseId,
  rows,
  isInstructor,
}: {
  courseId: string;
  rows: TopicRow[];
  isInstructor: boolean;
}) {
  if (rows.length === 0) {
    return (
      <div className="mb-6">
        <EmptyState
          title={
            isInstructor
              ? "Sınıfta henüz ölçülen konu yok. Öğrenciler onaylanmış sorulardan sınav provası çözdükçe konu bazlı durum burada görünür."
              : "Henüz ölçülen konu yok. Sınav provası çözdükçe konularının durumu burada görünür."
          }
          action={
            <Link
              href={`/courses/${courseId}/${isInstructor ? "questions" : "exam"}`}
              className="text-sm text-brand hover:text-brand-strong"
            >
              {isInstructor ? "Soru havuzuna git" : "Sınav provasına git"}
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <Card className="mb-6 p-0">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-medium text-fg">
          {isInstructor ? "Konu bazlı sınıf durumu" : "Konularım"}
        </h2>
        <span className="text-xs text-fg-subtle">önce zorlanılan konu</span>
      </div>
      <ul>
        {rows.map((row, index) => (
          <TopicRowItem key={row.topicId} row={row} rank={index + 1} />
        ))}
      </ul>
    </Card>
  );
}

/**
 * Kapsam dışı ret oranı (SC-005).
 *
 * Oran `null` olabilir; o zaman yerine sunucunun Türkçe `note`'u geçer, arayüz
 * kendi cümlesini de oranı da uydurmaz. `note` oran hesaplandığında da
 * gösteriliyor çünkü ORANIN TANIMINI o cümle veriyor (kanıt yetersizliğinin
 * paydaya girmediğini). `source` her hâlde yazılır: ölçümün nereden geldiği
 * görünmeden sayı raporlanmaz (Anayasa III).
 */
function OutOfScopeCard({ stat }: { stat: ClassAnalytics["out_of_scope"] }) {
  return (
    <Card className="mb-6">
      <h2 className="text-sm font-medium text-fg">Kapsam dışı ret oranı</h2>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-fg">
        {rateText(stat.rate)}
      </p>
      {stat.rate !== null && (
        <p className="prose-tr mt-2 text-sm text-fg-muted">
          {outOfScopeCountsText(stat)}
        </p>
      )}
      <p className="prose-tr mt-2 text-sm text-fg-muted">
        Kanıt yetersizliği ayrı sayılır: {stat.insufficient_context_count} istek.
      </p>
      <p className="prose-tr mt-2 text-xs text-fg-subtle">{stat.note}</p>
      <p className="mt-2 text-xs text-fg-subtle">
        Kaynak: {OUT_OF_SCOPE_SOURCE[stat.source]}
      </p>
    </Card>
  );
}

/**
 * Soru bazlı yanlış oranı.
 *
 * Bu ekran yazılırken uç, yanlışı olmayan soruları da listeye alıyordu (yalnız
 * `graded > 0` süzgeci vardı) ve COME 331'de dört satırdan birinin oranı %0'dı.
 * Başlık o gün veriye göre yazıldı — sonra ucun kendisi düzeltildi: liste artık
 * yalnız GERÇEKTEN yanlış yapılmış soruları taşıyor.
 *
 * Boş liste bu yüzden anlamlı bir cevaptır ve iki ayrı sebebi olabilir: hiç
 * değerlendirilmiş cevap yok, ya da var ama kimse yanlış yapmamış. Metin ikisini
 * birden karşılayacak biçimde yazılı — "veri yok" demek ikincisini gizlerdi.
 *
 * Oran her satırda PAYDASIYLA gösterilir: 3 cevaptan 2'si yanlış ile 300'den
 * 200'ü yanlış aynı şey değildir (Anayasa III).
 */
function MissedQuestions({
  questions,
}: {
  questions: ClassAnalytics["missed_questions"];
}) {
  return (
    <Card className="mb-6 p-0">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-medium text-fg">En çok yanlış yapılan sorular</h2>
      </div>
      {questions.length === 0 ? (
        <p className="prose-tr px-4 py-3 text-sm text-fg-muted">
          Yanlış yapılmış soru yok: ya henüz değerlendirilmiş cevap gelmedi ya da
          gelen cevapların hepsi doğruydu.
        </p>
      ) : (
        <ul>
          {questions.map((question) => (
            <li
              key={question.question_id}
              className="flex flex-wrap items-start gap-4 border-b border-border px-4 py-3 last:border-0"
            >
              <div className="min-w-0 flex-1">
                <p className="prose-tr text-sm text-fg">{question.stem}</p>
                <p className="mt-1 text-xs text-fg-subtle">{question.topic_name}</p>
              </div>
              <span className="shrink-0 font-mono text-sm text-fg">
                {missedRateText(question)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
