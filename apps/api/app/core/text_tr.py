"""Türkçe güvenli metin katlama — eşleştirme için tek kaynak.

Bu dosya 9 Ağustos'ta ÜÇÜNCÜ kopya yazılmak üzereyken açıldı. Aynı davranışın
(Türkçe küçültme + aksan sökme + tokenleştirme) iki ayrı uygulaması zaten vardı:

* `app/modules/assessment/socratic.py` — "sadece söyle" kalıplarını eşleştirmek için
* `app/modules/assessment/question_gen.py` — çeldirici→kaynak örtüşmesi için

Üçüncüsü `app/modules/retrieval/scope.py` için gerekiyordu. Anayasa XI'in kuralı
net: aynı davranış üçüncü kez yazılıyorsa ortak modüle çıkar. Ayrışan kopyaların
her zaman biri daha gevşek olur ve i/İ tuzağına ilk düşen o olur.

**Neden `str.lower()` yetmez.** Python'un `lower()`'ı Unicode kurallarını uygular,
Türkçe kurallarını değil:

    "I".lower()   -> "i"    (Türkçede "ı" olmalı)
    "İ".lower()   -> "i̇"    (i + U+0307 birleşik nokta; "i" ile EŞLEŞMEZ)

İkincisi sessiz bir hata sınıfıdır: iki metin gözle aynı görünür, karşılaştırma
False döner. Bu yüzden i/İ ve ı/I önce elle eşlenir, `lower()` sonra çağrılır.
`upper()` hiç kullanılmaz (Anayasa V).

**Neden aksan sökülüyor.** Öğrenci "çözüm" de yazar "cozum" da; materyal de her
iki yazımı taşıyabilir. Postgres tarafında `chunks.fts` kolonu zaten
`app.immutable_unaccent` üzerinden üretiliyor (`0001_core_schema.sql`), dolayısıyla
aksansız eşleşme veritabanının da varsayılanı. Buradaki katlama onun Python
karşılığıdır; birebir aynı ayrıştırıcı DEĞİLDİR ve öyle olduğu iddia edilmez —
bu modülü kullanan sinyaller kendi uygulamalarıyla kalibre edilir.
"""

from __future__ import annotations

import re
import unicodedata

#: Türkçeye özgü büyük→küçük eşlemesi. `lower()`'dan ÖNCE uygulanır.
_TR_LOWER = str.maketrans(
    {"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"}
)

#: Küçük harfli Türkçe karakterlerin ASCII karşılıkları.
_TR_ASCII = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})

_WORD = re.compile(r"[0-9a-z]+")


def fold(text: str) -> str:
    """Metni eşleştirilebilir tek biçime indirger.

    KULLANICIYA DÖNEN METİNDE KULLANILMAZ: bu fonksiyon bilgi kaybettirir
    ("çözüm" → "cozum"). Yalnız karşılaştırma tarafında kullanılır.
    """
    folded = unicodedata.normalize("NFC", text).translate(_TR_LOWER).lower()
    folded = folded.translate(_TR_ASCII)
    # Kalan aksanlı karakterler (Almanca ä, Fransızca é…) NFKD ile sökülür; Türkçe
    # harfler yukarıda zaten eşlendiği için bu adım onlara dokunmaz.
    decomposed = unicodedata.normalize("NFKD", folded)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokens(text: str, *, min_length: int = 1) -> list[str]:
    """Katlanmış metnin sözcükleri, geçtikleri sırayla.

    Sıra korunur (küme değil liste): çağıranların bir kısmı sıklık sayar, bir kısmı
    kümeye çevirir. Burada kümeye çevirmek, sayabilecek olandan bilgi alırdı.
    """
    return [word for word in _WORD.findall(fold(text)) if len(word) >= min_length]


__all__ = ["fold", "tokens"]
