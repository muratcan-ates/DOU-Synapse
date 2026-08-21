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
 */

import type { SourceInfo } from "@/components/source-card";
import type { QuestionStatus, QuestionType } from "@/lib/labels";

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
      quote: "fork() başarısızlıkta ebeveyne -1 döndürür ve yeni süreç yaratılmaz.",
    },
  },
];

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
