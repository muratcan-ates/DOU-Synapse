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
import type { LearningOutcome } from "@/lib/blueprint";
import { errorMessage } from "@/lib/errors";
import { QUESTION_STATUS, QUESTION_TYPE } from "@/lib/labels";
import { countByStatus, filterQuestions, nextDraftId, toQuestionView, type StatusFilter } from "@/lib/questions";
import { useSession } from "@/lib/session";
import type { Question, QuestionStatus, Topic } from "@/lib/types";
import { usePagedResource } from "@/lib/use-paged-resource";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Field } from "@/components/field";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, LoadMore, MetricRow, PageHeader } from "@/components/page-state";
import { AUTHORING_CONTROL_CLASS as SELECT_CLASS } from "@/components/question-authoring/classification-fields";
import { GeneratePanel } from "@/components/question-authoring/generate-panel";
import { QuestionDetail } from "@/components/question-authoring/question-detail";
import { Badge, Card, EmptyState } from "@/components/ui";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "Yüklenenlerin tümü" },
  { value: "draft", label: QUESTION_STATUS.draft.label },
  { value: "approved", label: QUESTION_STATUS.approved.label },
  { value: "rejected", label: QUESTION_STATUS.rejected.label },
];

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
  const { isInstructor, ready } = useSession(courseId);

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

      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={
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
        }
      >
        <QuestionPool key={courseId} courseId={courseId} />
      </InstructorGate>
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
  const fetchTopics = useCallback(
    () => api.get<Topic[]>(`/courses/${courseId}/topics`),
    [courseId],
  );
  const topicsResource = useResource(fetchTopics, [courseId]);
  const questionsResource = usePagedResource<Question>(
    `/courses/${courseId}/questions`,
    [courseId],
  );

  const authoring = useResource<{ enabled: boolean; outcomes: LearningOutcome[] }>(async () => {
    const capability = await api.get<{ enabled: boolean }>(`/courses/${courseId}/questions/authoring`);
    return { ...capability, outcomes: capability.enabled
      ? await api.get<LearningOutcome[]>(`/courses/${courseId}/learning-outcomes`) : [] };
  }, [courseId]);
  const [generating, setGenerating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  // Keep saved questions (including later pages) selected without reloading the
  // first page and losing the instructor's place in a large question pool.
  const [savedQuestions, setSavedQuestions] = useState<Record<string, { question: Question; base: Question | undefined }>>({});

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
  const error = topicsResource.error ?? questionsResource.error;
  const refreshError = topicsResource.refreshError ?? questionsResource.refreshError;
  const errorKind = topicsResource.errorKind ?? questionsResource.errorKind;
  const errorRequestId = topicsResource.errorRequestId ?? questionsResource.errorRequestId;
  const reload = useCallback(async () => {
    await Promise.all([topicsResource.reload(), questionsResource.reload()]);
  }, [topicsResource.reload, questionsResource.reload]);

  if (error)
    return (
      <ErrorNote
        message={error}
        kind={errorKind}
        requestId={errorRequestId}
        onRetry={reload}
      />
    );
  if (!topicsResource.data || !questionsResource.data) return <Loading />;

  const topics = topicsResource.data;
  const questions = questionsResource.data.map((question) => {
    const saved = savedQuestions[question.id];
    // A later server refresh is authoritative; local save responses only
    // replace the exact fetched row from which the edit started.
    return saved?.base === question ? saved.question : question;
  });
  function rememberQuestion(question: Question) {
    setSavedQuestions((current) => ({ ...current, [question.id]: {
      question, base: questionsResource.data?.find((item) => item.id === question.id),
    } }));
  }
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
    (selectedId ? questions.find((q) => q.id === selectedId) ?? savedQuestions[selectedId]?.question : undefined) ??
    visible[0] ??
    null;
  const outsideFilter = selected !== null && !visible.some((q) => q.id === selected.id);

  const topicName = (topicId: string) =>
    topics.find((topic) => topic.id === topicId)?.name ?? "Konu bulunamadı";

  async function decide(question: Question, status: Extract<QuestionStatus, "approved" | "rejected">) {
    if (busyId !== null || editingId !== null || generating) return;
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
      rememberQuestion(updated);
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

  /**
   * Soruyu havuzdan siler ve seçimi güvenli bir yere taşır.
   *
   * `decide` gibi `busyId` kullanmaz: onay kapısı `ConfirmAction`'ın kendi
   * `useSubmit`'inde ve hata metni tetikleyicinin yanında gösterilir. Buradaki
   * tek sorumluluk, silinen sorunun seçili kalmaması: satır artık yok, panel
   * onu göstermeye çalışırsa boş bir kabuk çizerdi.
   */
  async function removeQuestion(question: Question) {
    await api.delete(`/courses/${courseId}/questions/${question.id}`);
    const next = nextDraftId(questions, question.id);
    setSelectedId(next);
    setNotice(
      "Soru havuzdan silindi. Bu soruyu üreten belge, başka sorusu kalmadıysa artık silinebilir.",
    );
    setDecisionError(null);
    await reload();
  }

  /** Sıradaki taslağa geçiş KULLANICI eylemidir; odak da onunla taşınır. */
  function goToNextDraft(fromId: string) {
    if (editingId !== null || generating) return;
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
          { value: counts.draft, label: "Yüklenen onay bekleyen" },
          { value: counts.approved, label: "Yüklenen öğrenciye açık" },
          { value: counts.rejected, label: "Yüklenen reddedilen" },
          { value: counts.total, label: "Yüklenen soru" },
        ]}
      />
      <p className="prose-tr -mt-4 mb-6 text-xs text-fg-subtle">
        Sayılar ve süzgeçler yalnız bu ekranda yüklenen soruları kapsar. Daha fazla
        soru yüklendikçe güncellenir.
      </p>

      {(authoring.error ?? authoring.refreshError) && <ErrorNote
        message={authoring.error ?? authoring.refreshError ?? ""} kind={authoring.errorKind}
        requestId={authoring.errorRequestId} onRetry={authoring.reload} />}
      {editingId && <p role="status" className="mb-4 text-sm text-fg-muted">
        Düzenleme açık. Başka bir soru seçmeden veya üretmeden önce taslağı kaydedin ya da düzenlemeden vazgeçin.
      </p>}
      <GeneratePanel
        authoringEnabled={authoring.data?.enabled === true}
        outcomes={authoring.data?.outcomes ?? []}
        editing={editingId !== null}
        onGeneratingChange={setGenerating}
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
        <>
          {notice && <p role="status" className="mb-4 text-sm text-fg-muted">{notice}</p>}
          <EmptyState title="Havuzda henüz soru yok. Yukarıdan bir konu seçip soru üretin; üretilen sorular taslak olarak buraya düşer." />
        </>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
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
              <ul aria-label="Soru havuzu">
                {visible.map((question) => (
                  <QuestionRow
                    key={question.id}
                    question={question}
                    topic={topicName(question.topic_id)}
                    active={question.id === selected?.id}
                    disabled={editingId !== null || busyId !== null || generating}
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
              courseId={courseId}
              generating={generating}
              authoringEnabled={authoring.data?.enabled === true}
              outcomes={authoring.data?.outcomes ?? []}
              editing={editingId === selected.id}
              onEdit={() => {
                rememberQuestion(selected);
                setSelectedId(selected.id); setEditingId(selected.id);
                setNotice(null); setDecisionError(null);
              }}
              onCancelEdit={() => { setEditingId(null); setFocusRequest((n) => n + 1); }}
              onSaved={(updated) => {
                rememberQuestion(updated);
                setSelectedId(updated.id); setEditingId(null);
                setNotice("Taslak kaydedildi. Öğrenciye açmak için soruyu ayrıca onaylayın.");
                setFocusRequest((n) => n + 1);
              }}
              stemRef={stemRef}
              question={selected}
              topic={topicName(selected.topic_id)}
              outsideFilter={outsideFilter}
              busy={busyId === selected.id}
              notice={notice}
              decisionError={decisionError}
              hasNextDraft={nextDraftId(questions, selected.id) !== null}
              onDecide={(status) => decide(selected, status)}
              onDelete={() => removeQuestion(selected)}
              onNextDraft={() => goToNextDraft(selected.id)}
            />
          )}
        </div>
      )}
      <LoadMore
        hasMore={questionsResource.nextCursor !== null}
        busy={questionsResource.loadingMore}
        error={questionsResource.pageError}
        onLoadMore={() => void questionsResource.loadMore()}
      />
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
    <div role="group" aria-label="Yüklenen soruların durum süzgeci" className="flex w-fit flex-wrap gap-1 rounded-lg border border-border p-1">
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
  disabled,
  onSelect,
}: {
  question: Question;
  topic: string;
  active: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  const view = toQuestionView(question);
  const status = QUESTION_STATUS[question.status];

  return (
    <li>
      {/* Seçili satır kırmızı sol şeritle işaretli — kırmızının üç meşru
          kullanımından biri (aktif gösterge). */}
      <button
        onClick={() => { if (!disabled) onSelect(); }}
        aria-disabled={disabled}
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
