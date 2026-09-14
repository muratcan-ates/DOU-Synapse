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
 *
 * Kompozisyon (DESIGN.md "Modern akademik stüdyo grameri", 14 Eylül 2026):
 * sayfa tek odak alanıyla açılır (ölçünün tanımı + iki üç büyük sayı), altında
 * kompakt metrik şeridi, sonra konu listesi. Dört eşit metrik sayfayı açmaz.
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

/**
 * Bağlantı, satır içi eylem olarak buton gibi çizilir (DESIGN.md: düz metin
 * bağlantı değil, `Button size="sm"` görünümü). `href` ve metin değişmez;
 * `<a>` semantiği korunur, yalnız kabuk `Button variant="secondary" size="sm"`
 * ile aynıdır.
 */
const LINK_BUTTON_SM =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-border-strong bg-surface px-3 text-sm font-medium text-fg transition-[color,background,border,transform] duration-200 hover:border-fg-subtle hover:bg-surface-sunken active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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

      {/*
       * Veri yokken (yükleniyor, hata) ibare tek başına odak kartı olarak durur:
       * görünürlüğü isteğin başarısına bağlı değil.
       */}
      {!data && <FocusCard />}

      {data && (
        <>
          <FocusCard data={data} />
          <Summary data={data} />
          <UntrackedNote count={data.untracked_topics} />
          <TopicList
            courseId={courseId}
            rows={topicRows(data)}
            isInstructor={isInstructor}
          />
          {isClassAnalytics(data) && (
            <>
              <MissedQuestions questions={data.missed_questions} />
              <OutOfScopeCard stat={data.out_of_scope} />
            </>
          )}
        </>
      )}
    </>
  );
}

/**
 * Odak kartı: "Resmî not değildir" ibaresi + iki üç büyük sayı.
 *
 * İbare spec gereği ZORUNLU (ARCHITECTURE §5) ve sayıların ÜSTÜNDE durur: bu
 * ekranı açan kişi rakamları okumadan önce neye baktığını bilmeli. Veri gelmese
 * de, hata olsa da yerinde kalır. Ton nötr: bu bir uyarı değil, ölçünün tanımı.
 *
 * Sayılar sunucudan gelir; `average_score` null olabilir ve o zaman "Ölçüm yok"
 * yazar — 0 değil. Hiçbir sayı istemcide türetilmez.
 */
function FocusCard({ data }: { data?: StudentAnalytics | ClassAnalytics }) {
  const figures: Array<{ value: string | number; label: string }> = !data
    ? []
    : isClassAnalytics(data)
      ? [
          { value: scoreText(data.average_score), label: "Sınıf ortalaması" },
          { value: data.student_count, label: "Ölçüme giren öğrenci" },
          { value: data.tracked_topics, label: "Ölçülen konu" },
        ]
      : [
          { value: scoreText(data.average_score), label: "Genel skorun" },
          { value: data.needs_work_topics, label: "Çalışman gereken konu" },
        ];

  return (
    <Card className="mb-6">
      <p className="prose-tr max-w-[80ch] text-sm leading-relaxed text-fg-muted">
        <span className="font-medium text-fg">Bu gösterge resmî bir not değildir.</span>{" "}
        Nereye çalışılacağını gösteren pedagojik bir öneridir. Skor, son cevaplara
        daha çok ağırlık veren üstel bir ortalamayla hesaplanır ve alınan ipucu
        kademesi cevabın katkısını düşürür.
      </p>
      {figures.length > 0 && (
        <dl className="mt-6 flex flex-wrap gap-x-12 gap-y-6">
          {figures.map((figure) => (
            <div key={figure.label} className="flex min-w-32 flex-col-reverse gap-3">
              <dt className="text-sm font-medium text-fg-muted">{figure.label}</dt>
              <dd className="text-3xl leading-none font-semibold tracking-tight tabular-nums text-fg sm:text-4xl">
                {figure.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}

/**
 * Kompakt metrik şeridi: odak kartında olmayan ikincil sayılar.
 *
 * Sunucunun göndermediği hiçbir sayı burada türetilmez: "cevaplanan soru"
 * `answered_questions`'tan, "kapsam dışı ret oranı" `out_of_scope.rate`'ten
 * gelir; ikisi de istemcide yeniden sayılmaz.
 */
function Summary({ data }: { data: StudentAnalytics | ClassAnalytics }) {
  if (isClassAnalytics(data)) {
    return (
      <MetricRow
        items={[
          { value: data.answered_questions, label: "Cevaplanan soru" },
          { value: rateText(data.out_of_scope.rate), label: "Kapsam dışı ret oranı" },
          {
            value: data.out_of_scope.insufficient_context_count,
            label: "Kanıt yetersizliği",
          },
        ]}
      />
    );
  }
  return (
    <MetricRow
      items={[
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
 * Dolgu `--fg-subtle` (nötr), kanal `--border`: DESIGN.md §Known Gaps kategorik
 * analitik paletini henüz karara bağlamadı; renk bilgi taşımadığı için seviye
 * rozetten okunur. Kırmızı yok — ilerleme bir eylem değil.
 */
function TopicRowItem({ row, rank }: { row: TopicRow; rank: number }) {
  const level = MASTERY_LEVEL[row.level];
  return (
    <li className="px-5 py-5 transition-colors hover:bg-surface-sunken sm:px-6">
      <div className="flex items-center gap-3">
        <span className="w-6 shrink-0 text-xs tabular-nums text-fg-subtle">#{rank}</span>
        <p className="min-w-0 flex-1 break-words text-base font-medium leading-relaxed text-fg">{row.name}</p>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-fg">
          {scoreText(row.score)}
        </span>
      </div>
      {/* pl-9 = sıra sütunu (24px) + boşluk (12px): alt katman adla hizalanır. */}
      <div className="mt-3 flex flex-wrap items-center gap-3 pl-9">
        <div
          aria-hidden="true"
          className="h-2 min-w-16 flex-1 rounded-full bg-border"
        >
          <div
            className="h-2 rounded-full bg-fg-subtle transition-[width] duration-500 motion-reduce:transition-none"
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
          <span className="sr-only text-sm tabular-nums text-fg-subtle sm:not-sr-only">
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
 *
 * Kap `Card flat`: içinde kendi satır ayraçları olan liste; katmanı gölge değil
 * tek ince çerçeve taşır (saç çizgisi ızgarası yalnız gerçek liste satırlarında).
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
              className={LINK_BUTTON_SM}
            >
              {isInstructor ? "Soru havuzuna git" : "Sınav provasına git"}
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <Card variant="flat" padding="none" className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-5 sm:px-6">
        <h2 className="text-lg font-semibold text-fg">
          {isInstructor ? "Konu bazlı sınıf durumu" : "Konularım"}
        </h2>
        <span className="text-xs text-fg-muted">önce zorlanılan konu</span>
      </div>
      <ul className="divide-y divide-border border-t border-border">
        {rows.map((row, index) => (
          <TopicRowItem key={row.topicId} row={row} rank={index + 1} />
        ))}
      </ul>
    </Card>
  );
}

/**
 * Kapsam dışı ret oranı (SC-005) — tanım ve kaynak.
 *
 * Oranın kendisi metrik şeridinde; burası çukur yüzeyde duran alt bilgi: sayım,
 * ölçümün tanımı ve kaynağı. Oran `null` olabilir; o zaman sayım cümlesi
 * yazılmaz ve sunucunun Türkçe `note`'u tek açıklamadır, arayüz kendi cümlesini
 * de oranı da uydurmaz. `note` oran hesaplandığında da gösteriliyor çünkü ORANIN
 * TANIMINI o cümle veriyor (kanıt yetersizliğinin paydaya girmediğini).
 * `source` her hâlde yazılır: ölçümün nereden geldiği görünmeden sayı
 * raporlanmaz (Anayasa III).
 */
function OutOfScopeCard({ stat }: { stat: ClassAnalytics["out_of_scope"] }) {
  return (
    <Card variant="soft" className="mb-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-lg font-semibold text-fg">Kapsam dışı ret oranı</h2>
        <span className="text-2xl leading-none font-semibold tracking-tight tabular-nums text-fg">
          {rateText(stat.rate)}
        </span>
      </div>
      {stat.rate !== null && (
        <p className="prose-tr mt-3 text-sm text-fg-muted">
          {outOfScopeCountsText(stat)}
        </p>
      )}
      <p className="prose-tr mt-2 text-sm text-fg-muted">
        Kanıt yetersizliği ayrı sayılır:{" "}
        <span className="tabular-nums">{stat.insufficient_context_count}</span> istek.
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
 * 200'ü yanlış aynı şey değildir (Anayasa III). Sayılar sağa hizalı
 * `tabular-nums`; `font-mono` değil (Türkçe ayraç kopmasın).
 */
function MissedQuestions({
  questions,
}: {
  questions: ClassAnalytics["missed_questions"];
}) {
  return (
    <Card variant="flat" padding="none" className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-5 sm:px-6">
        <h2 className="text-lg font-semibold text-fg">En çok yanlış yapılan sorular</h2>
        {questions.length > 0 && (
          <span className="shrink-0 text-xs text-fg-muted">yanlış / değerlendirilen</span>
        )}
      </div>
      {questions.length === 0 ? (
        <p className="prose-tr border-t border-border px-5 py-4 text-sm text-fg-muted">
          Yanlış yapılmış soru yok: ya henüz değerlendirilmiş cevap gelmedi ya da
          gelen cevapların hepsi doğruydu.
        </p>
      ) : (
        <ul className="divide-y divide-border border-t border-border">
          {questions.map((question) => (
            <li
              key={question.question_id}
              className="flex flex-wrap items-start gap-4 px-5 py-5 sm:px-6"
            >
              <div className="min-w-0 flex-1">
                <p className="prose-tr text-base leading-relaxed text-fg">{question.stem}</p>
                <p className="mt-2 text-sm text-fg-subtle">{question.topic_name}</p>
              </div>
              <span className="shrink-0 text-right text-sm font-semibold tabular-nums text-fg">
                {missedRateText(question)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
