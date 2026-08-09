"""Çıktı temizliği — XSS ve ham teknik ayrıntı (T015).

Zincirin son halkası. İki ayrı tehdit var:

1. **Markdown/HTML enjeksiyonu.** Cevap metni ders materyalinden beslenir ve
   materyal güvenilmez girdidir; içinde `<img src=x onerror=...>` yazan bir satır
   olabilir. Frontend'in bunu güvenli işlediğine güvenmek yetmez — iki katman
   ucuzdur, tek katman bir gün unutulur.
2. **Ham teknik ayrıntı.** Yığın izi, bağlantı dizesi, anahtar: kullanıcıya
   gitmez (Anayasa X). Model bunları materyalden kopyalayarak da üretebilir.

Hassas kalıpların tanımı burada YENİDEN YAZILMAZ; `app.core.logging.redact`
kullanılır. Aynı kuralı iki dosyada tutmak, ikisinin zamanla ayrışması demektir
(Anayasa XI) — ve ayrışan taraf her zaman daha gevşek olanıdır.

Bilinçli takas: `redact` e-posta ve T.C. kimlik numarasını da maskeler. Materyal
içinde geçen bir e-posta adresi cevapta `[REDACTED_EMAIL]` görünür. Bu bir
kayıptır ama doğru yöndeki kayıptır: öğrenci materyalindeki kişisel veriyi
sohbet üzerinden yeniden yaymaktansa maskelemek yeğdir.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from dataclasses import replace

from app.contracts import Citation, GeneratedAnswer, GuardrailVerdict, RetrievedChunk
from app.core.logging import redact

BLOCK_REASON_EMPTY_AFTER_SANITIZE = "empty_after_sanitize"

_MAX_PASSES = 8

#: İçeriğiyle birlikte silinen ögeler: bunların gövdesi görüntülenecek metin değil,
#: yürütülecek yüktür.
_DANGEROUS_BLOCKS = re.compile(
    r"(?is)<\s*(script|style|iframe|object|embed|svg|math|template)\b.*?<\s*/\s*\1\s*>"
)
#: Kapanışı olmayan tehlikeli açılış etiketi de silinir; aksi hâlde gövde kalır.
_DANGEROUS_OPEN = re.compile(r"(?is)<\s*(?:script|style|iframe|object|embed|svg|math|template)\b")
_COMMENT_OR_DECL = re.compile(r"(?s)<!--.*?-->|<![^>]*>|<\?[^>]*\?>")
#: Etiket deseni bilerek dar: `<` işaretinden hemen sonra harf ya da `/` gelmesi
#: şart. Böylece "x < y > z" gibi matematiksel ifadeler yenmez, `<div>` yenir.
_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")

_DANGEROUS_SCHEME = re.compile(r"(?i)\b(?:javascript|vbscript|data)\s*:")
#: `[metin](javascript:...)` → yalnız metin kalır.
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\(\s*(?i:javascript|vbscript|data)\s*:[^)]*\)")

_STACK_TRACE_PATTERNS = (
    # Python yığın izi bloğu: girintili çerçeveler bittiğinde durur.
    re.compile(r"(?ms)^[ \t]*Traceback \(most recent call last\):.*?(?=^\S|\Z)"),
    re.compile(r'(?m)^[ \t]*File "[^"\n]+", line \d+.*$'),
    # Java / Node çerçeve satırı.
    re.compile(r"(?m)^[ \t]*at [\w.$<>]+\s*\([^)\n]*\)[ \t]*$"),
    # İstisna satırı, iki tanınabilir biçimde. Desenler bilerek dar: "3.2.1: Giriş"
    # gibi numaralı bölüm başlıkları da noktalı-ad-iki nokta şeklindedir ve
    # geniş bir desen onları da silerdi.
    re.compile(r"(?m)^[ \t]*[\w.]*\w(?:Error|Exception|Warning)\b\s*:.*$"),
    re.compile(r"(?m)^[ \t]*[\w.]*\.(?:errors?|exc|exceptions?)\.[\w.]+\s*:.*$"),
    re.compile(r"(?m)^[ \t]*(?:Exception|Caused by)\b.*$"),
)


def _strip_to_fixed_point(text: str) -> str:
    """Etiketleri sabit noktaya kadar söker.

    Tek geçiş yetmez: `<scr<script>ipt>` yazımında içteki etiket silinince
    dıştaki tamamlanır ve geriye çalışan bir `<script>` kalır. Döngü kendi
    çıktısını değiştirmediği anda durur.
    """
    for _ in range(_MAX_PASSES):
        previous = text
        text = _DANGEROUS_BLOCKS.sub(" ", text)
        text = _COMMENT_OR_DECL.sub(" ", text)
        text = _TAG.sub(" ", text)
        text = _DANGEROUS_OPEN.sub(" ", text)
        if text == previous:
            break
    return text


def clean(text: str) -> str:
    """Kullanıcıya gidecek metni temizler. Saf fonksiyon.

    Sıra önemlidir: HTML varlıkları ÖNCE çözülür, çünkü `&#106;avascript:` gibi
    kaçışlar çözülmeden taranırsa dedektörün altından geçer. Çözdükten sonra
    etiket sökümü sabit noktaya kadar döner.

    `str.upper()` benzeri bir dönüşüm burada ASLA yapılmaz: Türkçede i/İ bozulur
    (Anayasa V).
    """
    text = html.unescape(text)
    text = _strip_to_fixed_point(text)
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _DANGEROUS_SCHEME.sub("", text)

    for pattern in _STACK_TRACE_PATTERNS:
        text = pattern.sub("", text)

    text = redact(text)

    # Sökümlerden arta kalan boşlukları toparla; satır yapısı korunur çünkü
    # cevaplar paragraflı gelir.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def clean_citation(citation: Citation) -> Citation:
    """Atıf kartının GÖSTERİLEN üç alanını temizler.

    9 Ağustos'a kadar bu halka yalnız `answer.text`'e bakıyordu ve atıf kartı
    filtreden hiç geçmiyordu. Ölçüldü: `<script>alert(1)</script>` ve bir e-posta
    adresi taşıyan bir chunk, cevap metni tertemiz olsa bile kaynak kartında
    kullanıcıya olduğu gibi ulaşıyordu.

    Üç alan da güvenilmez girdiden beslenir ve üçü de ekranda görünür:

    * `quote` — chunk metninin kesiti, yani doğrudan ders materyali.
    * `file_name` — kullanıcının yüklediği dosyanın adı. `<img onerror=...>.pdf`
      diye bir dosya yüklemek hiçbir kuralı çiğnemez.
    * `location` — sayfa/slayt metninden türer.

    `chunk_id` temizlenmez ve temizlenmemelidir: UUID'dir, biz üretiriz, ve atıf
    doğrulamasının anahtarıdır — üzerinde yapılacak her dönüşüm set-membership'i
    bozar.

    Temizlik sonrası alıntı boşalırsa atıf DÜŞMEZ. Atfın değeri `chunk_id` ile
    dosya/konum metadata'sındadır; metni düşmanca diye geçerli bir kaynağı
    silmek, gösterilebilecek doğru bilgiyi de silmek olurdu (Anayasa I).
    """
    return replace(
        citation,
        file_name=clean(citation.file_name),
        location=clean(citation.location),
        quote=clean(citation.quote),
    )


def clean_citations(citations: Iterable[Citation]) -> list[Citation]:
    return [clean_citation(citation) for citation in citations]


class SanitizeGuardrail:
    """`Guardrail` protokolünü uygular. Zincirin üçüncü ve son halkası.

    `check()` yalnız METNİN kararını döner; atıf temizliği `clean_citations` ile
    ayrı yapılır ve uygulayan zincirdir (`chain.screen`). Sebep sözleşmedir:
    `GuardrailVerdict` yalnız `sanitized_text` taşır ve o dosya bu şeridin değil.
    Ayrım ayrıca zaten kurulu desene uyuyor — `check()` saf kalır, girdisini
    değiştirmez, kararı uygulamak çağıranın işidir.
    """

    def check(self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]) -> GuardrailVerdict:
        del retrieved  # bu halka yalnız metne bakar; imza protokol gereği ortaktır
        cleaned = clean(answer.text)

        if answer.text.strip() and not cleaned:
            # Metnin tamamı temizlikte gittiyse geriye gösterilecek bir şey yok.
            # "Boş cevap gönder" yerine blokla (Anayasa IV).
            return GuardrailVerdict(
                blocked=True,
                reason=BLOCK_REASON_EMPTY_AFTER_SANITIZE,
                sanitized_text="",
            )

        return GuardrailVerdict(
            blocked=False,
            sanitized_text=cleaned if cleaned != answer.text else None,
        )
