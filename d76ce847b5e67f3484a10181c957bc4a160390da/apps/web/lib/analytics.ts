/**
 * Analitik ekranının sözlüğü ve biçimlendiricileri — DOM'suz, saf.
 *
 * Bu ekranın tek zor işi bir sayı çizmek değil, **ölçülmemiş olanı ölçülmüş gibi
 * göstermemektir** (Anayasa III). O kural üç ayrı yerde bozulabilir: null bir
 * ortalamanın 0 gibi yazılması, çalışılmamış konunun 0.00 skorla listeye
 * girmesi, oranın paydasız gösterilmesi. Üçü de biçimlendirme kararıdır, yani
 * bileşenin içinde kalırsa yalnız tarayıcıda ve yalnız doğru veriyle gözlenir.
 * Buraya çıkarıldıkları için `analytics.test.ts` üçünü de doğrudan sınıyor.
 *
 * Seviye etiketi (`MASTERY_LEVEL`) burada, `lib/labels.ts`'teki
 * `masteryLevel(score)` fonksiyonunda DEĞİL: sunucu her satırda `level`
 * gönderiyor (`app/api/analytics.py`, `level_for`). İki taraf aynı eşiği ayrı
 * ayrı hesaplarsa eşik bir gün yalnız bir tarafta değişir ve arayüz sunucunun
 * "needs_work" dediği satıra "Orta" yazar. Skordan seviye türetmek bu ekranda
 * bilerek YAPILMIYOR; sunucudan gelen `level` etiketleniyor.
 */

import type { Tone } from "@/lib/labels";
import type {
  ClassAnalytics,
  MasteryLevel,
  MissedQuestion,
  OutOfScopeStat,
  StudentAnalytics,
} from "@/lib/types";

/**
 * Seviye etiketleri.
 *
 * "Geliştirilmeli" WARNING tonundadır, danger DEĞİL: düşük skor bir hata değil,
 * çalışma yönüdür. Kırmızı bu üründe hata rengi olarak kullanılmaz (DESIGN.md
 * kırmızı kilidi) ve öğrenciye "bozuksun" diyen bir renk göstermez.
 */
export const MASTERY_LEVEL: Record<MasteryLevel, { label: string; tone: Tone }> = {
  needs_work: { label: "Geliştirilmeli", tone: "warning" },
  medium: { label: "Orta", tone: "info" },
  good: { label: "İyi", tone: "success" },
};

/**
 * Ölçülmemiş değerin metni.
 *
 * Tek kelime değil iki kelime: metrik satırında 31px mono ile çizilir ve dar
 * ekranda tek uzun sözcük sarılamayıp hücreden taşar.
 */
export const NOT_MEASURED = "Ölçüm yok";

/** İstatistiğin kaynağı — sayının nereden geldiği görünmeden sayı yazılmaz. */
export const OUT_OF_SCOPE_SOURCE: Record<OutOfScopeStat["source"], string> = {
  request_logs: "istek kayıtları (request_logs)",
};

/**
 * 0-1 arası skor metni. Ondalık ayırıcı virgüldür (Anayasa V).
 *
 * `null` "ölçülmedi" demektir ve 0 ile ASLA karıştırılmaz: 0.00 ölçülmüş bir
 * başarısızlıktır, null ise hiç ölçüm olmamasıdır. `score ?? 0` yazan bir satır
 * ikisini tek görüntüde birleştirir ve öğrenciye hiç girmediği konudan sıfır
 * aldığını söyler.
 */
export function scoreText(score: number | null): string {
  if (score === null) return NOT_MEASURED;
  return score.toFixed(2).replace(".", ",");
}

/** 0-1 arası oranın yüzde metni. `null` oran uydurulmaz. */
export function rateText(rate: number | null): string {
  if (rate === null) return NOT_MEASURED;
  return `%${Math.round(rate * 100)}`;
}

/**
 * Çubuğun dolu yüzdesi (0-100 tam sayı).
 *
 * Kırpma savunma değil zorunluluk: `width: 140%` yazılırsa çubuk kabından taşar
 * ve satır düzeni bozulur. Kırpılan değer yalnız ÇİZİMİ etkiler; satırdaki
 * sayısal skor her zaman ham değerden yazılır.
 */
export function barPercent(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
}

/**
 * "Çalışılmamış konu" bildirimi.
 *
 * Bu konular listeye 0.00 ile GİRMEZ (sunucu da göndermiyor). Sayı olarak
 * söylenir, çünkü "bilmiyoruz" ile "kötüsün" farklı iki cümledir.
 */
export function untrackedNote(count: number): string | null {
  if (count <= 0) return null;
  return `${count} konu henüz çalışılmadı; bu konular için ölçüm yok ve listede yer almaz.`;
}

/**
 * Sınıf yanıtı mı öğrenci yanıtı mı?
 *
 * Ayrım rolden değil GÖVDEDEN yapılır. Rol istemcide `localStorage`'tan okunur
 * ve bir yetki belgesi değildir (Anayasa II); gövdeyi role bakarak daraltmak,
 * rolün yanlış olduğu tek karede var olmayan alanları okumak demektir.
 */
export function isClassAnalytics(
  data: StudentAnalytics | ClassAnalytics,
): data is ClassAnalytics {
  return "out_of_scope" in data;
}

/** Konu satırının çizim için normalleştirilmiş hâli. */
export interface TopicRow {
  topicId: string;
  name: string;
  score: number;
  level: MasteryLevel;
  answerCount: number;
  /** Yalnız sınıf görünümünde ölçülür; öğrenci görünümünde `null`. */
  studentCount: number | null;
}

/**
 * İki uçun konu listesini tek satır şekline indirger.
 *
 * SIRA KORUNUR — istemcide yeniden sıralanmaz. Sunucu ikisini de en düşük
 * skordan sıralıyor ("önce şuna bak"); burada ikinci bir sıralama kuralı
 * yazmak, iki tarafın bir gün farklı sıralamasına açık kapı bırakır.
 */
export function topicRows(data: StudentAnalytics | ClassAnalytics): TopicRow[] {
  if (isClassAnalytics(data)) {
    return data.topics.map((topic) => ({
      topicId: topic.topic_id,
      name: topic.name,
      score: topic.average_score,
      level: topic.level,
      answerCount: topic.answer_count,
      studentCount: topic.student_count,
    }));
  }
  return data.topics.map((topic) => ({
    topicId: topic.topic_id,
    name: topic.name,
    score: topic.score,
    level: topic.level,
    answerCount: topic.answer_count,
    studentCount: null,
  }));
}

/** Satırın hacmi: skorun kaç cevaba (ve sınıfta kaç öğrenciye) dayandığı. */
export function volumeText(row: TopicRow): string {
  const answers = `${row.answerCount} cevap`;
  return row.studentCount === null ? answers : `${answers} · ${row.studentCount} öğrenci`;
}

/**
 * Yanlış oranı ve PAYDASI birlikte.
 *
 * 3 cevaptan 2'si yanlış ile 300'den 200'ü yanlış aynı şey değildir; oran tek
 * başına ikisini ayırt edilemez kılar (Anayasa III). Payda `graded_answer_count`
 * yani yalnız DEĞERLENDİRİLEBİLMİŞ cevaplar — sunucu değerlendirilemeyeni
 * paydaya da koymuyor.
 */
export function missedRateText(question: MissedQuestion): string {
  return `${rateText(question.wrong_rate)} · ${question.graded_answer_count} değerlendirilen cevap`;
}

/** Kapsam dışı ret oranının payı ve paydası, cümle hâlinde. */
export function outOfScopeCountsText(stat: OutOfScopeStat): string {
  return `Cevap üretilen ${stat.answered_request_count} istekten ${stat.out_of_scope_count} tanesi kapsam dışı diye reddedildi.`;
}
