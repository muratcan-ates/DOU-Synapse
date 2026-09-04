import { useState } from "react";
import { api } from "@/lib/api";
import type { LearningOutcome } from "@/lib/blueprint";
import { QUESTION_TYPE } from "@/lib/labels";
import { classificationComplete, EMPTY_CLASSIFICATION, outcomesForTopic, type Classification } from "@/lib/question-authoring";
import { ANSWER_FORMAT, buildGenerateRequest, GENERATE_COUNTS, generationSummary, type GenerationSummary } from "@/lib/questions";
import type { AnswerFormat, QuestionGeneration, QuestionType, Topic } from "@/lib/types";
import { useSubmit } from "@/lib/use-submit";
import { Field } from "@/components/field";
import { ErrorNote } from "@/components/page-state";
import { Button, Card, Input } from "@/components/ui";
import { AUTHORING_CONTROL_CLASS as SELECT_CLASS, ClassificationFields } from "./classification-fields";

/**
 * Üretim çerçevesi — hocanın açık isteği: **çerçeveyi eğitmen kurar.**
 * Konu, soru tipi, cevap biçimi, adet ve isterse örnek sorular buradan gider
 * (`example_questions` sözleşmede vardı ama arayüzde yoksa özellik yok
 * demektir).
 */
export function GeneratePanel({
  authoringEnabled, outcomes, editing, onGeneratingChange,
  courseId,
  topics,
  onChanged,
  onGenerated,
}: {
  courseId: string;
  topics: Topic[];
  onChanged: () => Promise<void>;
  onGenerated: (report: QuestionGeneration) => void;
  onGeneratingChange: (busy: boolean) => void;
  authoringEnabled: boolean;
  outcomes: LearningOutcome[];
  editing: boolean;
}) {
  const [topicId, setTopicId] = useState<string>("");
  const [questionType, setQuestionType] = useState<QuestionType>("mcq");
  const [answerFormat, setAnswerFormat] = useState<AnswerFormat>("essay");
  const [count, setCount] = useState<number>(5);
  const [examplesText, setExamplesText] = useState("");
  const [summary, setSummary] = useState<GenerationSummary | null>(null);
  const [classification, setClassification] = useState<Classification>(EMPTY_CLASSIFICATION);

  // Seçili konu listeden düşmüş olabilir (başka sekmede silinen ders içeriği);
  // o durumda ilk konuya düşülür, boş bir `topic_id` gönderilmez.
  const activeTopicId =
    topicId && topics.some((topic) => topic.id === topicId) ? topicId : (topics[0]?.id ?? "");

  const { busy, error, submit } = useSubmit(async () => {
    onGeneratingChange(true);
    try {
      setSummary(null);
      const report = await api.post<QuestionGeneration>(
        `/courses/${courseId}/questions/generate`,
        buildGenerateRequest({
          topicId: activeTopicId,
          questionType,
          answerFormat,
          count,
          examplesText,
          ...(authoringEnabled ? classification : {}),
        }),
      );
      setSummary(generationSummary(report));
      onGenerated(report);
      await onChanged();
    } finally { onGeneratingChange(false); }
  }, "Soru üretilemedi.");

  function generate() {
    // Konu doğrulaması gönderim ÖNCESİ; çift-gönderim kapısı kancada.
    if (activeTopicId === "" || editing || (authoringEnabled && !classificationComplete(classification))) return;
    return submit();
  }

  return (
    <fieldset disabled={editing} className="min-w-0">
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
                  onChange={(e) => {
                    setTopicId(e.target.value);
                    if (!outcomesForTopic(outcomes, e.target.value).some((outcome) => outcome.id === classification.learningOutcomeId)) {
                      setClassification(EMPTY_CLASSIFICATION);
                    }
                  }}
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

          {authoringEnabled && <div className="mt-4">
            <ClassificationFields courseId={courseId} topicId={activeTopicId} outcomes={outcomes}
              value={classification} onChange={setClassification} />
          </div>}
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
            <Button variant="primary" aria-disabled={busy || editing || (authoringEnabled && !classificationComplete(classification))} onClick={generate}>
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
    </fieldset>
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

  // Buton `aria-disabled` ile beklemeye alınıyor (odağı kaybetmemek için);
  // `aria-disabled` gönderimi kendiliğinden engellemediğinden çift gönderim
  // kapısı `useSubmit`'te duruyor.
  const { busy, error, submit: create } = useSubmit(async () => {
    await api.post<Topic>(`/courses/${courseId}/topics`, { name });
    setName("");
    await onCreated();
  }, "Konu eklenemedi.");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    void create();
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
