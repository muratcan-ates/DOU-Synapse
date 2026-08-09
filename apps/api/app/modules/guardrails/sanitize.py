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

from app.contracts import GeneratedAnswer, GuardrailVerdict, RetrievedChunk
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
    re.compile(r"(?ms)^[ \t]*Traceback \(most recent call last\):.*?(?=^\S|\Z)"),
    re.compile(r'(?m)^[ \t]*File "[^"\n]+", line \d+.*$'),
    re.compile(r"(?m)^[ \t]*at [\w.$<>]+\s*\([^)\n]*\)[ \t]*$"),
    re.compile(r"(?m)^[ \t]*\w+(?:\.\w+)+(?:Error|Exception)\b.*$"),
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


class SanitizeGuardrail:
    """`Guardrail` protokolünü uygular. Zincirin üçüncü ve son halkası."""

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
