/**
 * Önizleme ekranlarının örnek verisi — tek yerde.
 *
 * Motoru henüz bağlanmamış ekranlar (sohbet, sınav, soru havuzu, ilerleme)
 * örnek veriyle çalışıyor. Veri sayfaların İÇİNDE dururken iki sorun vardı:
 * bileşen dosyaları uzuyordu ve örnek veri gerçek veriden ayırt edilemiyordu.
 * Burada toplanınca sınır nettir: bu dosya silinince önizleme kalmaz.
 *
 * Sayılar ve metinler sample_data/isletim-sistemleri paketiyle tutarlıdır;
 * uydurma dosya adı veya sayfa numarası kullanılmaz.
 *
 * Sayfa numaraları `evaluation/gold_set/{calibration,holdout}.json` içindeki
 * doğrulanmış `expected_sources` kayıtlarıyla karşılaştırılarak yazıldı
 * (o dosyalar gerçek ingest koşusuna karşı `verify_gold_set.py` ile sınandı).
 * Önizleme de olsa konum uydurulmaz: ürünün tek iddiası "kaynağı şu sayfa".
 */

import type { SourceInfo } from "@/components/source-card";
import type { QuestionStatus, QuestionType } from "@/lib/types";

export interface PreviewQuestion {
  id: string;
  topic: string;
  type: QuestionType;
  status: QuestionStatus;
  stem: string;
  options?: string[];
  answerKey: string;
  source: SourceInfo;
}

export const PREVIEW_QUESTIONS: PreviewQuestion[] = [
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
      // "Sayfa 2" yazıyordu: quantum ödünleşimi materyalin 1. sayfasında.
      // Kanıt: gold_set/holdout.json → "Quantum'un çok küçük seçilmesi hangi
      // maliyetleri artırır" → 02-cpu-scheduling.pdf, page_number 1.
      fileName: "02-cpu-scheduling.pdf",
      location: "Sayfa 1",
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
      // "Sayfa 2" yazıyordu: sayfalama/ofset anlatımı 1. sayfada, 2. sayfa
      // TLB ve sayfa değiştirme algoritmalarına ayrılmış. Kanıt:
      // gold_set/holdout.json → "Bir sayfa tablosu girdisi hangi kontrol
      // bitlerini taşır" → 03-memory-management.pdf, page_number 1.
      fileName: "03-memory-management.pdf",
      location: "Sayfa 1",
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
      quote: "fork() başarısızlıkta ebeveyne -1 döndürür ve yeni süreç yaratılmaz.",
    },
  },
  /*
   * Aşağıdaki üçü onaylanmış çoktan seçmeli sorulardır ve sınav önizlemesini
   * besleyen tek kaynak budur (bkz. EXAM_PREVIEW_QUESTIONS). Sınav ekranına
   * ayrı bir soru listesi geri eklenmesin: aynı adı taşıyan ama farklı şekilde
   * olan ikinci bir liste, iki ekranın sessizce ayrışmasını üretiyordu.
   */
  {
    id: "S-006",
    topic: "CPU zamanlama",
    type: "mcq",
    status: "approved",
    stem: "Round Robin zamanlamada quantum süresinin çok büyük seçilmesinin doğrudan sonucu nedir?",
    options: [
      "Zamanlama pratikte FCFS'ye yaklaşır ve yanıt süresi kötüleşir",
      "Bağlam değiştirme sıklığı artar ve verim çöker",
      "Kısa süreçler süresiz olarak ertelenir",
      "Deadlock olasılığı doğrudan artar",
    ],
    answerKey: "Zamanlama pratikte FCFS'ye yaklaşır ve yanıt süresi kötüleşir",
    source: {
      fileName: "02-cpu-scheduling.pdf",
      location: "Sayfa 1",
      quote:
        "Quantum çok büyükse RR, pratikte First-Come-First-Served'e (FCFS) yaklaşır ve yanıt süresi kötüleşir.",
    },
  },
  {
    id: "S-007",
    topic: "Bellek yönetimi",
    type: "mcq",
    status: "approved",
    stem: "Sayfalama kullanan bir sistemde sayfa hatası (page fault) hangi anda oluşur?",
    options: [
      "İstenen sayfa fiziksel bellekte bulunmadığında",
      "Sayfa tablosu tamamen dolduğunda",
      "Süreç kendi adres uzayının dışına yazmaya çalıştığında",
      "Bağlam değiştirme sırasında her zaman",
    ],
    answerKey: "İstenen sayfa fiziksel bellekte bulunmadığında",
    source: {
      fileName: "03-memory-management.pdf",
      location: "Sayfa 1",
      quote:
        "Erişilen sayfa şu an fiziksel bellekte değilse donanım bir tuzak (trap) üretir; işletim sistemi sayfayı diskten yükler, sayfa tablosunu günceller ve komutu yeniden çalıştırır.",
    },
  },
  {
    id: "S-008",
    topic: "Senkronizasyon",
    type: "mcq",
    status: "approved",
    stem: "Mutex ile korunan bir kritik bölgede aşağıdakilerden hangisi tanımsız davranışa yol açar?",
    options: [
      "Kilidi alan thread'in kritik bölge sonunda kilidi kendisinin açması",
      "Kilidi alan thread dışında bir thread'in kilidi açmaya çalışması",
      "Kritik bölge içinde paylaşımlı veriye yazılması",
      "Kilit alınmadan önce yerel bir değişkenin okunması",
    ],
    answerKey: "Kilidi alan thread dışında bir thread'in kilidi açmaya çalışması",
    source: {
      fileName: "04-synchronization.pdf",
      location: "Sayfa 1",
      quote:
        "Mutex'i kilitleyen thread onu açmalıdır; başka bir thread'in kilidini açmaya çalışması tanımsız davranıştır.",
    },
  },
];

/** Şıkları kesin olan soru — sınav ekranı şıksız soru çizemez. */
export type ExamPreviewQuestion = PreviewQuestion & { options: string[] };

/**
 * Sınav önizlemesinin soruları: havuzun ONAYLANMIŞ çoktan seçmeli soruları.
 *
 * Filtre kozmetik değil, ürün kuralının kendisidir: "onaylanmayan soru öğrenci
 * akışında hiç görünmez" (soru havuzu ekranında yazılı). Ayrı bir sınav listesi
 * tutulsaydı bu kural iki yerde ayrı ayrı hatırlanmak zorunda kalırdı ve
 * reddedilmiş S-005 er geç sınava sızardı (Anayasa XI).
 */
export const EXAM_PREVIEW_QUESTIONS: ExamPreviewQuestion[] =
  PREVIEW_QUESTIONS.filter(
    (q): q is ExamPreviewQuestion =>
      q.type === "mcq" && q.status === "approved" && q.options !== undefined,
  );

export interface PreviewTopic {
  name: string;
  /** 0-1 arası EWMA skoru */
  score: number;
  answers: number;
}

export const STUDENT_TOPICS: PreviewTopic[] = [
  { name: "Deadlock", score: 0.32, answers: 6 },
  { name: "Bellek yönetimi", score: 0.48, answers: 4 },
  { name: "CPU zamanlama", score: 0.71, answers: 9 },
  { name: "Senkronizasyon", score: 0.78, answers: 5 },
  { name: "Süreçler ve thread'ler", score: 0.86, answers: 11 },
];

export const CLASS_TOPICS: PreviewTopic[] = [
  { name: "Deadlock", score: 0.38, answers: 84 },
  { name: "Senkronizasyon", score: 0.52, answers: 61 },
  { name: "Bellek yönetimi", score: 0.63, answers: 73 },
  { name: "CPU zamanlama", score: 0.74, answers: 96 },
  { name: "Süreçler ve thread'ler", score: 0.81, answers: 108 },
];

/**
 * Kapsam dışı ret (abstention) oranı — 0-1 arası.
 *
 * Analitik ekranında "%7" diye gömülüydü. Örnek veri üretim kodundan ayrı
 * dosyada durur (Anayasa XI): sınır ancak bu dosya silinerek sınanabiliyorsa
 * gerçektir, ekrana serpiştirilen tek bir sabit o sınırı deler.
 */
export const ABSTENTION_RATE = 0.07;

export const MISSED_QUESTIONS = [
  {
    topic: "Deadlock",
    stem: "Banker's algoritmasında güvenli durum ne demektir?",
    wrongRate: 0.68,
  },
  {
    topic: "Senkronizasyon",
    stem: "wait() çağrısı mutex içinde yapılırsa ne olur?",
    wrongRate: 0.61,
  },
  {
    topic: "Bellek yönetimi",
    stem: "Sayfa hatası (page fault) hangi anda oluşur?",
    wrongRate: 0.54,
  },
];
