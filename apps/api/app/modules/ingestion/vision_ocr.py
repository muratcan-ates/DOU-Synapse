"""Metinsiz (taranmış / el yazısı) PDF sayfalarını görsel modelle transkribe eder.

Neden var: 15 Eylül'de gerçek bir ders notu (tablet üzerine el yazısı, matematik
notasyonu, çizimler) yüklendi ve `parse_pdf` doğru olarak "metin yok" dedi.
Tesseract bu tür sayfada anlamsız karakter üretir; o çöp parçalanıp gömülürse
öğrenci anlamsız bir metne atıf görür — "kaynak yoksa cevap yok" diyen bir
sistem için sessiz zehir. Görsel model (Gemini Flash) el yazısını ve LaTeX'i
okuyabiliyor; risk, formülü sessizce bozması. O risk üç yerde tutuluyor:

1. Prompt harfi harfine transkripsiyon ister, düzeltmeyi ve tahmini yasaklar;
   okunamayan yer `[okunamadı]` olur, çizimler transkribe edilmez.
2. `[okunamadı]` sayısı/oranı eşiği aşan sayfa DÜŞÜK KALİTE sayılır; hiçbir
   sayfa geçmezse belge reddedilir (bugünkü davranışa düşer, çöp üretmez).
3. Her blok `AI okuması` köken etiketi taşır; atıf yüzeyleri bunu gösterir.

Ağ çağrısı bu modülün içinde kalır; `parsers.parse` yalnız bir `transcriber`
çağrılabilir alır, böylece ayrıştırıcı saf ve ağsız test edilebilir kalır.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from dataclasses import dataclass

#: Sayfa render ölçeği: 2x ≈ 144 DPI. Daha düşükte `x[n-1]`'deki eksi ve kesir
#: çizgisi kayboluyor; daha yüksek çözünürlük token'ı artırıp doğruluğa katkı
#: yapmıyor (Gemini'ın kendi ölçümü). Uzun kenar A4'te ~1700px.
RENDER_ZOOM = 2.0
JPEG_QUALITY = 85
UNREADABLE = "[okunamadı]"
#: Sayfa başına bu kadar `[okunamadı]` ya da bu oran aşılırsa sayfa düşük kalite.
MAX_UNREADABLE_PER_PAGE = 4
MAX_UNREADABLE_RATIO = 0.08
#: Bu kadar karakter bile okunamadıysa sayfa boş sayılır.
MIN_PAGE_CHARS = 40
ORIGIN_LABEL = "AI okuması (el yazısı/tarama)"

SYSTEM_PROMPT = """Sen bir akademik OCR ve transkripsiyon motorusun.
Görevin, paylaşılan ders notu sayfasındaki el yazısı, basılı metin, matematiksel
ifadeler ve çizimleri HİÇBİR YORUM VE DÜZELTME YAPMADAN ham metne dökmektir.

KURALLAR:
1. SADAKAT: Nottaki mantık veya işlem hatalarını asla düzeltme. Ne görüyorsan
   harfi harfine aktar. Tahmin yürütme, problem çözme, tamamlama yapma.
2. DİL: Metin Türkçe ve İngilizce karışık olabilir. Tercüme etme; orijinal dili
   ve imlayı koru.
3. MATEMATİK: Tüm matematiksel ifadeleri LaTeX olarak yaz ($inline$ veya
   $$display$$). Ayrık zamanlı sinyal indislerini köşeli parantezle aktar:
   x[n], h[n], u[n], \\delta[n]. Parçalı fonksiyon, matris ve integralleri tam
   LaTeX sözdizimiyle aç (\\begin{cases} ... \\end{cases}).
4. ÇİZİMLER: Blok diyagram, sinyal grafiği veya geometrik çizimi transkribe
   etmeye çalışma. Yerine yalnız şunu koy: [çizim: <kısa teknik özet>]
5. VURGULAR: Renkli kalemle altı çizilmiş veya kutu içine alınmış kısımları
   **kalın** işaretle.
6. BELİRSİZLİK: Net okuyamadığın her kelime/sembol yerine İSTİSNASIZ yalnız
   [okunamadı] yaz. Asla uydurma.
7. ÇIKTI: Doğrudan transkripsiyonla başla. Selamlama, özet, açıklama ekleme."""

USER_PROMPT = "Bu ders notu sayfasını yukarıdaki kurallara tam uyarak transkribe et."

#: `parsers.PageTranscriber` ile aynı sözleşme: (sayfa_no, jpeg) -> transkript.
Transcriber = Callable[[int, bytes], str]
#: Görsel okumanın sayfa üst sınırı; config'teki `ocr_vlm_max_pages` bunu geçemez.
MAX_VISION_PAGES = 40


@dataclass(frozen=True, slots=True)
class PageTranscript:
    page_number: int
    text: str
    unreadable: int
    low_quality: bool


def render_pages(content: bytes, *, max_pages: int) -> list[bytes]:
    """PDF sayfalarını JPEG baytlarına çevirir (sayfa başına bir görüntü)."""
    import pymupdf

    document = pymupdf.open(stream=content, filetype="pdf")
    try:
        if document.page_count > max_pages:
            raise ValueError(
                f"PDF {document.page_count} sayfa; görsel okuma üst sınırı {max_pages}."
            )
        matrix = pymupdf.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        # Açık `page_count` döngüsü: `pymupdf.Document` çalışma zamanında
        # yinelenebilir ama tip bilgisi bunu söylemiyor ve `mypy app` tüm paket
        # için duruyor. Aynı tuzak `parse_pdf`'te de yorumla işaretli.
        return [
            document.load_page(index)
            .get_pixmap(matrix=matrix, alpha=False)
            .tobytes("jpeg", jpg_quality=JPEG_QUALITY)
            for index in range(document.page_count)
        ]
    finally:
        document.close()


def assess(page_number: int, text: str) -> PageTranscript:
    """Kural tabanlı belirsizlik: modelin kendi güven skoru güvenilir değil,
    `[okunamadı]` sayımı ise ek maliyetsiz ve ölçülebilir."""
    cleaned = text.strip()
    unreadable = cleaned.count(UNREADABLE)
    words = [w for w in re.split(r"\s+", cleaned) if w]
    ratio = unreadable / len(words) if words else 1.0
    readable_chars = len(cleaned.replace(UNREADABLE, "").strip())
    low = (
        readable_chars < MIN_PAGE_CHARS
        or unreadable > MAX_UNREADABLE_PER_PAGE
        or ratio > MAX_UNREADABLE_RATIO
    )
    return PageTranscript(
        page_number=page_number, text=cleaned, unreadable=unreadable, low_quality=low
    )


def gemini_transcriber(*, model: str, api_key: str, timeout_seconds: float = 90.0) -> Transcriber:
    """litellm üzerinden tek sayfa → metin. Anahtar açıkça verilir, ortamdan okunmaz."""
    import litellm

    def transcribe(page_number: int, image: bytes) -> str:
        data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        response = litellm.completion(
            model=model,
            api_key=api_key,
            temperature=0,
            timeout=timeout_seconds,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        choice = response.choices[0].message
        content = choice.content if isinstance(choice.content, str) else ""
        return content or ""

    return transcribe
