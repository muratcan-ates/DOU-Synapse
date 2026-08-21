"use client";

/**
 * Soru havuzu ve eğitmen onayı (T035). Uçlar: `GET/POST /courses/{id}/topics`,
 * `GET /courses/{id}/questions`, `POST .../questions/generate`,
 * `POST .../questions/{qid}/approve|reject`.
 *
 * Ürünün en güçlü vaadi bu ekranda görünür hâle gelir: **yapay zekâ üretir,
 * eğitmen yayınlar.** Üretilen her soru `draft` doğar ve onaysız hiçbir soru
 * öğrenci akışına girmez (canlı doğrulandı: öğrenci kimliğiyle aynı uç yalnız
 * `approved` soruları ve beyaz listeden geçmiş payload'ı döndürüyor).
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
 * `payload` daraltması burada DEĞİL `lib/questions.ts`'te: jsonb'yi JSX'in
 * ortasında eşelemek okunmaz olur ve yalnız tarayıcıda sınanabilirdi
 * (bkz. `lib/questions.test.ts`).
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { QUESTION_STATUS, QUESTION_TYPE } from "@/lib/labels";
import {
  ANSWER_FORMAT,
  buildGenerateRequest,
  countByStatus,
  filterQuestions,
  GENERATE_COUNTS,
  generationSummary,
  nextDraftId,
  toQuestionView,
  type GenerationSummary,
  type QuestionView,
  type StatusFilter,
} from "@/lib/questions";
import { useSession } from "@/lib/session";
import type {
  AnswerFormat,
  Question,
  QuestionGeneration,
  QuestionStatus,
  QuestionType,
  Topic,
} from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Field } from "@/components/field";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { SourceCard } from "@/components/source-card";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

/**
 * `<select>` kabuğu — `ui.tsx`'teki `Input` ile birebir aynı ölçüler: 44px
 * yükseklik (DESIGN.md §Responsive dokunma hedefi), 8px köşe, 1px kenarlık,
 * aynı odak halkası. Aynı sabit `members/page.tsx`'te de var; ikisi de
 * `ui.tsx`'e `Select` olarak taşınmalı (Anayasa XI), ama o dosya bu görevde
 * başka bir sahiplikte. Raporda isteniyor.
 */
const SELECT_CLASS =
  "h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "Tümü" },
  { value: "draft", label: QUESTION_STATUS.draft.label },
  { value: "approved", label: QUESTION_STATUS.approved.label },
  { value: "rejected", label: QUESTION_STATUS.rejected.label },
];

interface PoolData {
  topics: Topic[];
  questions: Question[];
}

export default function QuestionsPage() {
  return (
    <AppShell>
      <QuestionsView />
    </AppShell>
  );
}

function QuestionsView() {
  const { courseId } = useParams<{ courseId: string }>();
  /*
   * Rol kapısı yalnız ARAYÜZÜ şekillendirir; güvenlik kontrolü DEĞİLDİR.
   * Yetki her zaman sunucuda doğrulanır (Anayasa II): bu ekranın beslendiği
   * dört yazma ucu da `require_course_instructor`'dan geçer — öğrenci isteği
   * burada hiçbir kapı olmasa bile 403 döner (canlı doğrulandı: "Bu işlem
   * yalnızca dersin eğitmeni tarafından yapılabilir."). Kapının işi güvenlik
   * değil dürüstlük: öğrenciye çalışmayan bir eğitmen formu göstermemek
   * (Anayasa XI).
   *
   * `ready` gelmeden hiçbir dala girilmez (Anayasa IV, fail-closed): rol
   * localStorage'dan ilk efektte okunur, o ana kadar "eğitmen değil" varsayımı
   * eğitmene bir kare boyunca yanlış ekran gösterirdi.
   */
  const { isInstructor, ready } = useSession();

  return (
    <div>
      <CourseNav courseId={courseId} />

      <PageHeader
        title="Soru havuzu"
        description={
          isInstructor
            ? "Sistem soruları ders materyalinden üretir ve taslak olarak buraya düşürür. Onaylamadığınız hiçbir soru öğrenciye görünmez."
            : undefined
        }
      />

      {!ready ? (
        <Loading />
      ) : isInstructor ? (
        <QuestionPool courseId={courseId} />
      ) : (
        /*
         * Sekme öğrenciye gösterilmiyor (course-nav.tsx `instructorOnly`) ama
         * adres çubuğuna yazılarak girilebiliyor. Kırmızı/uyarı yok: yetkisi
         * olmayan sayfaya girmek arıza değil, sakin bir yönlendirme konusudur.
         */
        <EmptyState
          title="Soru havuzu yalnızca dersin eğitmenine gösterilir. Onaylanan sorular sınav provasında karşınıza çıkar."
          action={
            <Link
              href={`/courses/${courseId}/exam`}
              className="text-sm text-brand hover:text-brand-strong"
            >
              Sınav provasına git
            </Link>
          }
        />
      )}
    </div>
  );
}

/**
 * Havuzun kendisi — yalnız eğitmen dalında mount edilir.
 *
 * Ayrı bileşen olmasının sebebi kozmetik değil: `useResource` mount olur olmaz
 * istek atar. Kapı aynı bileşenin içinde olsaydı öğrenci de GET atardı.
 */
function QuestionPool({ courseId }: { courseId: string }) {
  const fetchPool = useCallback(async (): Promise<PoolData> => {
    const [topics, questions] = await Promise.all([
      api.get<Topic[]>(`/courses/${courseId}/topics`),
      api.get<Question[]>(`/courses/${courseId}/questions`),
    ]);
    return { topics, questions };
  }, [courseId]);

  const { data, error, refreshError, errorKind, errorRequestId, reload } = useResource(
    fetchPool,
    [courseId],
  );

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  /** Son kararın cümlesi: hem yazılır hem `role="status"` ile duyurulur. */
  const [notice, setNotice] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const stemRef = useRef<HTMLHeadingElement>(null);
  /*
   * Odak isteği bir sayaçtır, doğrudan `focus()` çağrısı değil.
   * `requestAnimationFrame` denendi ve tutmadı: React yeni soruyu boyamadan
   * önce kare gelebiliyor ve odak eski düğmede kalıyordu (tarayıcıda ölçüldü).
   * Efekt commit'ten SONRA koşar, yani başlık o an gerçekten yerindedir.
   */
  const [focusRequest, setFocusRequest] = useState(0);
  useEffect(() => {
    if (focusRequest > 0) stemRef.current?.focus();
  }, [focusRequest]);

  // `error` yalnız elde veri YOKKEN dolar (bkz. use-resource.ts); tazeleme
  // hatası ekranı kapatmaz, aşağıda satır içinde gösterilir.
  if (error)
    return (
      <ErrorNote
        message={error}
        kind={errorKind}
        requestId={errorRequestId}
        onRetry={reload}
      />
    );
  if (!data) return <Loading />;

  const { topics, questions } = data;
  const counts = countByStatus(questions);
  const visible = filterQuestions(questions, statusFilter, topicFilter);

  /*
   * Seçim TAM listeden çözülür, süzülmüş listeden değil. Sebebi karar anında
   * görünür: "Taslak" süzgeciyle çalışan eğitmen bir soruyu onayladığında o
   * soru süzgecin dışına çıkar; seçim süzülmüş listeye bağlı olsaydı panel
   * sessizce başka bir soruya kayardı (bulgu 14) ve eğitmen neyi onayladığını
   * göremezdi. Soru yerinde kalır, süzgeç dışına düştüğü ise ayrıca yazılır.
   */
  const selected =
    (selectedId ? questions.find((q) => q.id === selectedId) : undefined) ??
    visible[0] ??
    null;
  const outsideFilter = selected !== null && !visible.some((q) => q.id === selected.id);

  const topicName = (topicId: string) =>
    topics.find((topic) => topic.id === topicId)?.name ?? "Konu bulunamadı";

  async function decide(question: Question, status: Extract<QuestionStatus, "approved" | "rejected">) {
    if (busyId !== null) return;
    // Karar sonrası soru süzgeç dışına düşse bile panelde kalsın diye seçim
    // sabitlenir; bu satır olmadan seçim `visible[0]`'a düşerdi.
    setSelectedId(question.id);
    setBusyId(question.id);
    setDecisionError(null);
    try {
      const action = status === "approved" ? "approve" : "reject";
      const updated = await api.post<Question>(
        `/courses/${courseId}/questions/${question.id}/${action}`,
      );
      // Etiket `lib/labels.ts`'ten gelir; ikinci bir durum sözlüğü yazılmaz.
      setNotice(
        status === "approved"
          ? `Soru onaylandı. Bu soru artık öğrencilere görünüyor. Durum: ${QUESTION_STATUS[updated.status].label}.`
          : `Soru reddedildi. Havuzda kalır ama öğrenciye gösterilmez. Durum: ${QUESTION_STATUS[updated.status].label}.`,
      );
      await reload();
    } catch (e) {
      setDecisionError(errorMessage(e, "Karar kaydedilemedi."));
    } finally {
      setBusyId(null);
    }
  }

  /** Sıradaki taslağa geçiş KULLANICI eylemidir; odak da onunla taşınır. */
  function goToNextDraft(fromId: string) {
    const next = nextDraftId(questions, fromId);
    if (next === null) return;
    setSelectedId(next);
    setNotice(null);
    setDecisionError(null);
    // Panel içeriği tümüyle değişti: odak yeni sorunun başlığına taşınmazsa
    // klavye kullanıcısı altındaki her şeyin başkalaştığını fark etmez.
    setFocusRequest((n) => n + 1);
  }

  return (
    <>
      <MetricRow
        items={[
          { value: counts.draft, label: "Onay bekleyen" },
          { value: counts.approved, label: "Öğrenciye açık" },
          { value: counts.rejected, label: "Reddedilen" },
          { value: counts.total, label: "Toplam soru" },
        ]}
      />

      <GeneratePanel
        courseId={courseId}
        topics={topics}
        onChanged={reload}
        onGenerated={(report) => {
          // Yeni taslaklar listenin başına düşer; seçimi ilkine taşımak
          // kullanıcının bakmak isteyeceği yere götürür ve sessiz değil:
          // üretim raporu zaten ekranda duruyor.
          const first = report.questions?.[0];
          if (first) setSelectedId(first.id);
        }}
      />

      {refreshError && (
        <ErrorNote
          message={refreshError}
          kind={errorKind}
          requestId={errorRequestId}
          onRetry={reload}
        />
      )}

      {questions.length === 0 ? (
        <EmptyState title="Havuzda henüz soru yok. Yukarıdan bir konu seçip soru üretin; üretilen sorular taslak olarak buraya düşer." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
          <Card className="h-fit p-0">
            <div className="space-y-3 border-b border-border px-4 py-3">
              <h2 className="text-sm font-medium text-fg">Üretilen sorular</h2>
              <StatusTabs
                value={statusFilter}
                counts={counts}
                onChange={setStatusFilter}
              />
              {topics.length > 1 && (
                <Field label="Konu süzgeci">
                  {(control) => (
                    <select
                      {...control}
                      value={topicFilter}
                      onChange={(e) => setTopicFilter(e.target.value)}
                      className={SELECT_CLASS}
                    >
                      <option value="all">Tüm konular</option>
                      {topics.map((topic) => (
                        <option key={topic.id} value={topic.id}>
                          {topic.name}
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
              )}
            </div>

            {visible.length === 0 ? (
              <p className="px-4 py-6 text-sm text-fg-muted">
                Bu süzgeçte soru yok.
              </p>
            ) : (
              <ul>
                {visible.map((question) => (
                  <QuestionRow
                    key={question.id}
                    question={question}
                    topic={topicName(question.topic_id)}
                    active={question.id === selected?.id}
                    onSelect={() => {
                      setSelectedId(question.id);
                      setNotice(null);
                      setDecisionError(null);
                    }}
                  />
                ))}
              </ul>
            )}
          </Card>

          {selected && (
            <QuestionDetail
              stemRef={stemRef}
              question={selected}
              topic={topicName(selected.topic_id)}
              outsideFilter={outsideFilter}
              busy={busyId === selected.id}
              notice={notice}
              decisionError={decisionError}
              hasNextDraft={nextDraftId(questions, selected.id) !== null}
              onDecide={(status) => decide(selected, status)}
              onNextDraft={() => goToNextDraft(selected.id)}
            />
          )}
        </div>
      )}
    </>
  );
}

/**
 * Durum süzgeci. Sayılar etiketin yanında duruyor: "Taslak" sekmesine basmadan
 * kaç taslak olduğu görünmezse eğitmen her sekmeyi tek tek dener.
 */
function StatusTabs({
  value,
  counts,
  onChange,
}: {
  value: StatusFilter;
  counts: { draft: number; approved: number; rejected: number; total: number };
  onChange: (next: StatusFilter) => void;
}) {
  const countOf = (filter: StatusFilter) =>
    filter === "all" ? counts.total : counts[filter];

  /*
   * Segment düğmesinin dili `chat/page.tsx`'teki mod seçicisiyle BİREBİR aynı:
   * kenarlıklı bir grup, seçili olan `border-strong` + `font-medium` + `--fg`.
   * Kırmızı kullanılmadı — süzgeç, kırmızının üç meşru işinden (birincil eylem,
   * aktif navigasyon, kurum işareti) hiçbiri değil. İki ekranda aynı desen var;
   * üçüncüsü yazılırken ortak bileşene çıkmalı (Anayasa XI, raporda).
   */
  return (
    <div role="group" aria-label="Durum süzgeci" className="flex w-fit flex-wrap gap-1 rounded-lg border border-border p-1">
      {STATUS_FILTERS.map((filter) => {
        const active = filter.value === value;
        return (
          <button
            key={filter.value}
            type="button"
            onClick={() => onChange(filter.value)}
            aria-pressed={active}
            className={`h-8 rounded-md border px-3 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              active
                ? "border-border-strong bg-surface font-medium text-fg"
                : "border-transparent text-fg-muted hover:text-fg"
            }`}
          >
            {filter.label} ({countOf(filter.value)})
          </button>
        );
      })}
    </div>
  );
}

function QuestionRow({
  question,
  topic,
  active,
  onSelect,
}: {
  question: Question;
  topic: string;
  active: boolean;
  onSelect: () => void;
}) {
  const view = toQuestionView(question);
  const status = QUESTION_STATUS[question.status];

  return (
    <li>
      {/* Seçili satır kırmızı sol şeritle işaretli — kırmızının üç meşru
          kullanımından biri (aktif gösterge). */}
      <button
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className={`w-full border-b border-l-2 border-border px-4 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
          active
            ? "border-l-brand bg-brand-subtle/40"
            : "border-l-transparent hover:bg-brand-subtle/20"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-fg-subtle">{QUESTION_TYPE[question.type]}</span>
          <Badge tone={status.tone}>{status.label}</Badge>
        </div>
        <p className="prose-tr mt-1.5 line-clamp-2 text-sm text-fg">
          {view.stem ?? "Soru metni bu kayıtta yok."}
        </p>
        <p className="mt-1 text-xs text-fg-subtle">{topic}</p>
      </button>
    </li>
  );
}

function QuestionDetail({
  stemRef,
  question,
  topic,
  outsideFilter,
  busy,
  notice,
  decisionError,
  hasNextDraft,
  onDecide,
  onNextDraft,
}: {
  stemRef: React.RefObject<HTMLHeadingElement | null>;
  question: Question;
  topic: string;
  outsideFilter: boolean;
  busy: boolean;
  notice: string | null;
  decisionError: string | null;
  hasNextDraft: boolean;
  onDecide: (status: "approved" | "rejected") => void;
  onNextDraft: () => void;
}) {
  const view = toQuestionView(question);
  const status = QUESTION_STATUS[question.status];

  return (
    <Card>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{QUESTION_TYPE[question.type]}</Badge>
        <Badge tone={status.tone}>{status.label}</Badge>
        {view.answerFormat && (
          <Badge tone="neutral">{ANSWER_FORMAT[view.answerFormat]}</Badge>
        )}
        <span className="text-xs text-fg-subtle">{topic}</span>
      </div>

      {outsideFilter && (
        <p className="mb-4 text-xs text-fg-muted">
          Bu soru seçili süzgeçte görünmüyor; kararınızı görebilesiniz diye
          panelde tutuluyor.
        </p>
      )}

      {/*
        Panelin başlığı soru metnidir; "sıradaki taslağa geç" sonrası odak
        buraya taşınır, bu yüzden `tabIndex={-1}` (klavye sırasına GİRMEZ,
        yalnız programla odaklanabilir).
      */}
      <h2
        ref={stemRef}
        tabIndex={-1}
        className="prose-tr rounded-lg text-lg font-normal text-fg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
      >
        {view.stem ?? "Soru metni bu kayıtta yok."}
      </h2>

      <QuestionBody view={view} />

      <div className="mt-6">
        <h3 className="mb-2 text-xs font-medium text-fg-muted">
          Üretimde kullanılan kaynak
        </h3>
        {view.source ? (
          <SourceCard source={view.source} />
        ) : (
          /*
            Kaynağı olmayan soru bir hata ekranı değil ama sessiz de geçilmez:
            onay kararı "bu materyalde gerçekten var mı" sorusudur ve kaynak
            görünmüyorsa eğitmen onu göremeden onaylamamalı (Anayasa I).
          */
          <p className="rounded-lg border border-border bg-bg px-4 py-3 text-sm text-fg-muted">
            Bu sorunun kaynak parçası okunamadı. Kaynağı görmeden onaylamayın.
          </p>
        )}
      </div>

      {/*
        `disabled` yerine `aria-disabled`: tarayıcı devre dışı bırakılan öğeden
        odağı <body>'ye atar, yani kararı veren klavye kullanıcısı odağını
        tamamen kaybederdi. `Button` aria-disabled'ta tıklamayı zaten yutuyor
        (components/ui.tsx).
      */}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
        <Button
          variant="primary"
          aria-disabled={busy || question.status === "approved"}
          onClick={() => onDecide("approved")}
        >
          {question.status === "approved" ? "Onaylandı" : "Onayla ve öğrenciye aç"}
        </Button>
        <Button
          variant="secondary"
          aria-disabled={busy || question.status === "rejected"}
          onClick={() => onDecide("rejected")}
        >
          {question.status === "rejected" ? "Reddedildi" : "Reddet"}
        </Button>
        {hasNextDraft && (
          <Button variant="ghost" onClick={onNextDraft}>
            Sıradaki taslağa geç
          </Button>
        )}
      </div>

      <p className="mt-3 text-xs text-fg-subtle">
        Onaylanmayan soru öğrenci akışında hiç görünmez.
      </p>

      {/*
        Karar sonucu: hem görünür hem duyurulur. `role="status"` örtük olarak
        polite'tır — karar bir hata değildir, `alert` kullanılmaz.
      */}
      <p role="status" className="mt-2 text-xs text-fg-muted">
        {busy ? "Karar kaydediliyor…" : (notice ?? "")}
      </p>

      {decisionError && <ErrorNote message={decisionError} />}
    </Card>
  );
}

/** Tipe göre değişen gövde: şıklar, kod, cevap anahtarı, rubrik. */
function QuestionBody({ view }: { view: QuestionView }) {
  return (
    <>
      {view.options.length > 0 && (
        <ul className="mt-5 space-y-2">
          {view.options.map((option) => (
            <li
              key={option.key}
              className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${
                option.correct
                  ? "border-success bg-success-bg text-fg"
                  : "border-border text-fg-muted"
              }`}
            >
              {/* Renk tek başına bilgi taşımaz: doğru şıkta metin de var. */}
              <span className="mt-0.5 w-14 shrink-0 text-xs text-fg-subtle">
                {option.key}
                {option.correct ? " · doğru" : ""}
              </span>
              <span className="prose-tr">{option.text}</span>
            </li>
          ))}
        </ul>
      )}

      {view.code && (
        <div className="mt-5">
          <h3 className="mb-2 text-xs font-medium text-fg-muted">
            Kod{view.code.language ? ` · ${view.code.language}` : ""}
          </h3>
          <pre className="overflow-x-auto rounded-lg border border-border bg-bg px-4 py-3">
            <code className="font-mono text-xs text-fg">{view.code.code}</code>
          </pre>
        </div>
      )}

      {view.answerKey && (
        <Section title="Cevap anahtarı">
          <p className="prose-tr rounded-lg border border-border bg-bg px-4 py-3 text-sm text-fg">
            {view.answerKey}
          </p>
        </Section>
      )}

      {view.bugAnswer && (
        <Section title="Cevap anahtarı">
          <dl className="space-y-1 rounded-lg border border-border bg-bg px-4 py-3 text-sm">
            <Row label="Hatalı satır" value={view.bugAnswer.line?.toString() ?? null} />
            <Row label="Hata türü" value={view.bugAnswer.bugType} />
            <Row label="Düzeltme" value={view.bugAnswer.fixSummary} />
          </dl>
        </Section>
      )}

      {view.acceptedAnswers.length > 0 && (
        <Section title="Kabul edilen karşılıklar">
          <div className="flex flex-wrap gap-2">
            {view.acceptedAnswers.map((answer) => (
              <span
                key={answer}
                className="rounded-sm border border-border bg-bg px-2.5 py-0.5 font-mono text-xs text-fg-muted"
              >
                {answer}
              </span>
            ))}
          </div>
        </Section>
      )}

      {view.keyPoints.length > 0 && (
        <Section title="Cevapta aranan noktalar">
          <ul className="space-y-1">
            {view.keyPoints.map((point) => (
              <li key={point} className="prose-tr text-sm text-fg-muted">
                · {point}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {view.rubric.length > 0 && (
        <Section title="Puanlama ölçütü">
          <dl className="space-y-1">
            {view.rubric.map((item) => (
              <div key={item.point} className="flex items-baseline justify-between gap-3">
                <dt className="prose-tr text-sm text-fg-muted">{item.point}</dt>
                <dd className="font-mono text-xs text-fg-subtle">{item.weight}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {view.explanation && (
        <Section title="Gerekçe">
          <p className="prose-tr text-sm text-fg-muted">{view.explanation}</p>
        </Section>
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="mb-2 text-xs font-medium text-fg-muted">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  if (value === null) return null;
  return (
    <div className="flex items-baseline gap-2">
      <dt className="shrink-0 text-xs text-fg-subtle">{label}</dt>
      <dd className="prose-tr text-fg">{value}</dd>
    </div>
  );
}

/**
 * Üretim çerçevesi — hocanın açık isteği: **çerçeveyi eğitmen kurar.**
 * Konu, soru tipi, cevap biçimi, adet ve isterse örnek sorular buradan gider
 * (`example_questions` sözleşmede vardı ama arayüzde yoksa özellik yok
 * demektir).
 */
function GeneratePanel({
  courseId,
  topics,
  onChanged,
  onGenerated,
}: {
  courseId: string;
  topics: Topic[];
  onChanged: () => Promise<void>;
  onGenerated: (report: QuestionGeneration) => void;
}) {
  const [topicId, setTopicId] = useState<string>("");
  const [questionType, setQuestionType] = useState<QuestionType>("mcq");
  const [answerFormat, setAnswerFormat] = useState<AnswerFormat>("essay");
  const [count, setCount] = useState<number>(5);
  const [examplesText, setExamplesText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<GenerationSummary | null>(null);

  // Seçili konu listeden düşmüş olabilir (başka sekmede silinen ders içeriği);
  // o durumda ilk konuya düşülür, boş bir `topic_id` gönderilmez.
  const activeTopicId =
    topicId && topics.some((topic) => topic.id === topicId) ? topicId : (topics[0]?.id ?? "");

  async function generate() {
    if (busy || activeTopicId === "") return;
    setBusy(true);
    setError(null);
    setSummary(null);
    try {
      const report = await api.post<QuestionGeneration>(
        `/courses/${courseId}/questions/generate`,
        buildGenerateRequest({
          topicId: activeTopicId,
          questionType,
          answerFormat,
          count,
          examplesText,
        }),
      );
      setSummary(generationSummary(report));
      onGenerated(report);
      await onChanged();
    } catch (e) {
      setError(errorMessage(e, "Soru üretilemedi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <h2 className="text-sm font-medium text-fg">Soru üret</h2>
      <p className="prose-tr mt-1 text-xs text-fg-muted">
        Çerçeveyi siz kurarsınız: konu, tip ve biçim sizin seçiminiz. Sistem
        yalnız ders materyalinden üretir ve her soruyu taslak olarak bırakır.
      </p>

      {topics.length === 0 ? (
        <p className="mt-4 text-sm text-fg-muted">
          Soru üretimi bir konuya bağlanır. Aşağıdan ilk konuyu ekleyin.
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Konu">
              {(control) => (
                <select
                  {...control}
                  value={activeTopicId}
                  onChange={(e) => setTopicId(e.target.value)}
                  className={SELECT_CLASS}
                >
                  {topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>

            <Field label="Soru tipi">
              {(control) => (
                <select
                  {...control}
                  value={questionType}
                  onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                  className={SELECT_CLASS}
                >
                  {(Object.keys(QUESTION_TYPE) as QuestionType[]).map((type) => (
                    <option key={type} value={type}>
                      {QUESTION_TYPE[type]}
                    </option>
                  ))}
                </select>
              )}
            </Field>

            {/*
              Cevap biçimi yalnız "Açık uçlu" tipte anlamlı ve yalnız o tipte
              gönderiliyor: sunucu diğer tiplerde 422 döndürüyor. Alanı her
              zaman göstermek, çalışmayan bir seçim sunmak olurdu (Anayasa XI).
            */}
            {questionType === "open" && (
              <Field label="Cevap biçimi">
                {(control) => (
                  <select
                    {...control}
                    value={answerFormat}
                    onChange={(e) => setAnswerFormat(e.target.value as AnswerFormat)}
                    className={SELECT_CLASS}
                  >
                    {(Object.keys(ANSWER_FORMAT) as AnswerFormat[]).map((format) => (
                      <option key={format} value={format}>
                        {ANSWER_FORMAT[format]}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            )}

            {/* Serbest sayı girdisi yok: sözleşme 1-20 arasını kabul ediyor ve
                geçersiz bir sayının hiç oluşmaması, sonra reddedilmesinden iyi. */}
            <Field label="Kaç soru">
              {(control) => (
                <select
                  {...control}
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                  className={SELECT_CLASS}
                >
                  {GENERATE_COUNTS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>

          <div className="mt-3">
            <Field label="Örnek sorular (isteğe bağlı, her satır bir soru)">
              {(control) => (
                <textarea
                  {...control}
                  value={examplesText}
                  onChange={(e) => setExamplesText(e.target.value)}
                  rows={3}
                  className={`${SELECT_CLASS} h-auto py-2 leading-6`}
                />
              )}
            </Field>
            <p className="mt-1 text-xs text-fg-subtle">
              Verirseniz üretim bu üslubu ve zorluk düzeyini taklit eder. En fazla
              beş satır gönderilir.
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button variant="primary" aria-disabled={busy} onClick={generate}>
              {busy ? "Üretiliyor…" : "Soru üret"}
            </Button>
            <p role="status" className="text-xs text-fg-muted">
              {busy ? "Materyal taranıyor ve sorular hazırlanıyor…" : ""}
            </p>
          </div>
        </>
      )}

      {error && (
        <div className="mt-3">
          <ErrorNote message={error} />
        </div>
      )}

      {summary && <GenerationReport summary={summary} />}

      {/* Konu ekleme ikincil eylemdir: asıl akış "konu seç, üret". Formu üste
          koymak, her gelişte önce boş bir metin kutusu okutuyordu. */}
      <NewTopicForm courseId={courseId} onCreated={onChanged} />
    </Card>
  );
}

/**
 * Üretim muhasebesi — gizlenmez (Anayasa III).
 *
 * `returned: 0` bir çökme DEĞİLDİR: sağlayıcı şemaya uyan soru döndürmediğinde
 * ya da konuyla eşleşen materyal bulunamadığında sistem uydurmak yerine boş
 * dönüyor (fail-closed, Anayasa IV). Bu yüzden ton nötr, kırmızı yok, ünlem
 * yok, `role="alert"` yok — abstention'ın hata gibi gösterilmemesiyle aynı
 * karar (DESIGN.md). `role="status"` örtük olarak polite'tır: rapor belirince
 * ekran okuyucu araya girmeden okur.
 *
 * Gerekçe listesi neden `accepted`/`rejected`'a değil kendi uzunluğuna bağlı:
 * sunucu deneme düzeyindeki hataları da bu diziye yazıyor ve o durumda üç sayı
 * da sıfır kalıyor. Canlı gövde (materyalsiz ders): `{"requested":3,
 * "returned":0,"accepted":0,"rejected":0,"rejection_reasons":["konuyla eşleşen
 * ders materyali bulunamadı"]}` — koşul `rejected > 0` olsaydı eğitmen "3
 * istedim, 0 geldi" görüp sebebi hiç göremezdi.
 *
 * Gerekçe metinleri sunucudan Türkçe gelir ve BİREBİR yazılır; arayüz kendi
 * açıklamasını uydurmaz (Anayasa V: hata metnini backend üretir).
 */
function GenerationReport({ summary }: { summary: GenerationSummary }) {
  return (
    <div
      role="status"
      className="mt-4 rounded-lg border border-border bg-bg px-4 py-3"
    >
      <h3 className="text-xs font-medium text-fg-muted">Üretim raporu</h3>
      <p className="prose-tr mt-1 text-sm text-fg">{summary.sentence}</p>

      {summary.accepted === 0 && (
        <p className="prose-tr mt-2 text-sm text-fg-muted">
          Bu turda havuza soru eklenmedi. Bu bir arıza değil: sistem
          doğrulayamadığı bir soruyu yazmaktansa hiçbir şey yazmıyor.
          {summary.reasons.length > 0
            ? " Sunucunun bildirdiği gerekçeler aşağıda."
            : " Sunucu bu tur için ayrıca bir gerekçe bildirmedi."}
        </p>
      )}

      {summary.reasons.length > 0 && (
        <div className="mt-3">
          <h4 className="text-xs font-medium text-fg-muted">Eleme gerekçeleri</h4>
          <ul className="mt-1 space-y-0.5">
            {summary.reasons.map((reason) => (
              <li key={reason.text} className="prose-tr text-xs text-fg-muted">
                · {reason.text}
                {/*
                  Tekrar sayısı yalnız birden büyükse yazılır ve gerekçe
                  metnine karışmasın diye mono/soluk durur. Sayı ölçülmüş bir
                  değerdir (dizideki tekrar), uydurma değil.
                */}
                {reason.count > 1 && (
                  <span className="ml-1.5 font-mono text-fg-subtle">
                    {reason.count} kez
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Konu ekleme — soru üretimi `topic_id` istediği için havuzun ön koşulu. */
function NewTopicForm({
  courseId,
  onCreated,
}: {
  courseId: string;
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    // Buton `aria-disabled` ile beklemeye alınıyor (odağı kaybetmemek için);
    // `aria-disabled` gönderimi kendiliğinden engellemediğinden çift gönderim
    // kapısı burada duruyor.
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post<Topic>(`/courses/${courseId}/topics`, { name });
      setName("");
      await onCreated();
    } catch (e) {
      setError(errorMessage(e, "Konu eklenemedi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-end"
    >
      <div className="flex-1">
        <Field label="Yeni konu">
          {(control) => (
            <Input
              {...control}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Deadlock"
              minLength={2}
              maxLength={200}
              required
            />
          )}
        </Field>
      </div>
      <Button type="submit" variant="secondary" aria-disabled={busy}>
        {busy ? "Ekleniyor…" : "Konu ekle"}
      </Button>
      {error && <ErrorNote message={error} />}
    </form>
  );
}
