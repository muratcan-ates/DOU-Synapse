"""Materyalden kavram haritası: parçalar ve aralarındaki bağlantılar.

## Ne yapıyor, ne yapmıyor

Dersin işlenmiş belgelerinden **anahtar terimleri** ve hangi terimlerin aynı
pasajda birlikte anlatıldığını çıkarır. Model çağrılmaz; çıktının tamamı
materyalin kendisinden türetilir ve her terim gerçek bir chunk'a bağlanır.
Yorum, tanım ya da özet ÜRETİLMEZ — terimin yanında duran cümle materyalde
yazan cümledir.

Bu, "kaynak yoksa cevap yok" ilkesinin bu yüzeydeki karşılığıdır: kavram
haritası bir iddia değil, bir dizindir.

## Sıralama neden TF-IDF değil

İlk akla gelen TF-IDF'tir ve burada YANLIŞ cevabı verir. TF-IDF bir terimi
"az belgede geçiyorsa değerli" sayar; oysa bir dersin merkezî kavramı tanımı
gereği çoğu pasajda geçer. İşletim Sistemleri materyalinde `süreç` neredeyse
her sayfadadır ve listenin BİRİNCİ sırasında olmalıdır — TF-IDF onu en dibe
atardı.

Bu yüzden sıralama **kaç ayrı pasajda geçtiğine** göredir: bir terim ne kadar
çok pasajda anlatılıyorsa dersin o kadar merkezindedir. Üst sınır KONMADI
(bilerek): "çok geçiyorsa gereksizdir" kuralı tam da merkezî kavramı silerdi.
Gürültüyü alt eşik (`_MIN_CHUNK_COUNT`) ve işlev sözcüğü listesi eler.

## Türkçe ekler: gövdeleme yerine önek birleştirme

`süreç`, `süreçler`, `süreçlerin`, `süreçte` ayrı terim sayılsaydı liste aynı
kavramı dört kez gösterirdi. Gerçek bir gövdeleyici (stemmer) bağımlılık ister
(`ENGEL: bağımlılık`), bu yüzden Türkçenin eklemeli yapısını kullanan kaba ama
ölçülebilir bir kural uygulanır: **kısa bir son ek dışında bir terim diğerinin
öneki ise, uzun olan kısa olana katılır.**

İki koruma yanlış birleşmeyi sınırlar:

- Gövde en az `_MERGE_MIN_STEM` (5) karakter olmalı. Bu olmasaydı `veri`,
  `veritabani`'nı yutardı — ikisi ayrı kavram.
- Ek en fazla `_MERGE_MAX_SUFFIX` (4) karakter olmalı. `sayfa` + `lama`
  birleşir (kabul edilebilir), `kanal` + `izasyon` birleşmez.

Kabul edilen bedel yazılı olsun: bu kural bir gövdeleyici değildir. Sesli
düşmesi (`akıl`/`aklın`) ve ünsüz yumuşaması (`kitap`/`kitabı`) yakalanmaz;
o çiftler ayrı terim olarak görünür. Ekranda bu sınır kullanıcıya söylenir.

## Bağlantılar

İki terim aynı pasajda geçiyorsa aralarında bir kenar vardır ve ağırlığı kaç
pasajı paylaştıklarıdır. Bu, "sistem düşüncesi" katmanıdır: parçalar terimler,
bütün ise hangi parçaların birlikte anlatıldığıdır. Anlamsal bir ilişki iddiası
DEĞİLDİR — yalnız birlikte geçme sayısıdır ve ekranda öyle adlandırılır.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import text_tr
from app.models.core import Chunk, Document, DocumentStatus
from app.modules.retrieval.stopwords_tr import STOPWORDS

#: Terim en az bu kadar ayrı pasajda geçmeli. Tek pasajda geçen sözcük bir
#: kavram değil, bir cümledir.
_MIN_CHUNK_COUNT = 2

#: Katlanmış terimin en az uzunluğu. Üçün altı Türkçede neredeyse tamamen
#: işlev sözcüğüdür ve liste onları tek tek saymak zorunda kalırdı.
_MIN_TERM_LENGTH = 4

#: Önek birleştirmesinin iki koruması (gerekçe modül başlığında).
_MERGE_MIN_STEM = 5
_MERGE_MAX_SUFFIX = 4

#: Ekrana ve dışa aktarıma giren üst sınırlar. Kavram haritası bir dizin değil
#: özettir; 40 terimden sonrası okunmuyor.
MAX_TERMS = 40
MAX_EDGES = 60

#: Tek koşuda okunacak en fazla pasaj. Büyük derste sorgu ve bellek sınırı;
#: aşılırsa sonuç "kısmi" olarak işaretlenir, sessizce kesilmez.
MAX_CHUNKS = 2000

#: Yüzey biçimini korumak için ayrı desen: `text_tr.tokens` katlar ve özgün
#: yazımı kaybeder, oysa ekranda "süreç" görünmeli, "surec" değil.
_SURFACE_WORD = re.compile(r"[0-9A-Za-zÇĞİÖŞÜÂÎÛçğıöşüâîû]+")


@dataclass(frozen=True, slots=True)
class ConceptTerm:
    """Bir anahtar terim ve onu en iyi anlatan pasaj."""

    #: Katlanmış anahtar; birleştirme ve kenarlar bunun üstünden çalışır.
    key: str
    #: Ekranda görünen yazım: materyalde en sık geçen yüzey biçimi.
    surface: str
    #: Kaç ayrı pasajda geçtiği. Sıralama ölçütü.
    chunk_count: int
    #: Toplam geçiş sayısı. Eşitlik bozucu.
    total_count: int
    #: Terimin en yoğun geçtiği pasaj; kaynak kartı buradan üretilir.
    chunk_id: UUID


@dataclass(frozen=True, slots=True)
class ConceptEdge:
    """İki terimin birlikte geçtiği pasaj sayısı. Anlamsal ilişki iddiası değil."""

    left: str
    right: str
    chunk_count: int


@dataclass(frozen=True, slots=True)
class ConceptMap:
    terms: list[ConceptTerm]
    edges: list[ConceptEdge]
    #: Haritanın dayandığı pasaj sayısı — ekranda "neye bakıldığı" yazılır.
    chunk_count: int
    #: `MAX_CHUNKS` aşıldığı için pasajların bir kısmı okunmadıysa True.
    truncated: bool


@dataclass(frozen=True, slots=True)
class ChunkText:
    """Çıkarımın tek girdisi. Saf katmanın veritabanını tanımaması için ayrı tip."""

    chunk_id: UUID
    text: str


# ---------------------------------------------------------------------------
# Saf çıkarım
# ---------------------------------------------------------------------------


def _surface_tokens(text: str) -> list[tuple[str, str]]:
    """(katlanmış anahtar, özgün yüzey) çiftleri. Sayılar ve kısa sözcükler düşer.

    İşlev sözcükleri burada ELENMEZ, birleştirmeden sonra elenir. Sebebi ölçüldü:
    `tablo` elenip `tablosu` elenmeyince liste çekimli bir işlev sözcüğünü terim
    sanıyordu. Önce birleştirip sonra temsilciye bakmak bu sızıntıyı kapatır.
    """
    pairs: list[tuple[str, str]] = []
    for surface in _SURFACE_WORD.findall(text):
        key = text_tr.fold(surface)
        if len(key) < _MIN_TERM_LENGTH or key.isdigit():
            continue
        pairs.append((key, surface))
    return pairs


def _merge_target(key: str, stems: frozenset[str] | set[str]) -> str | None:
    """`key`'in katılacağı gövdeyi bulur; yoksa None.

    Gövde listesini taramak yerine `key`'in OLASI öneklerine bakılır: geçerli
    gövde uzunluğu `max(5, len-4) .. len-1` aralığındadır, yani en çok dört
    aday. Tarama O(gövde sayısı) idi ve işlev sözcükleri de haritaya girince
    binlerce anahtar için kareseldi; bu biçim anahtar başına sabit zamandır.

    En UZUN uygun önek seçilir: `süreçlerin` hem `süreç` hem `süreçler` ile
    eşleşir ve `süreçler` de `süreç`'e katılacağı için zincir doğru yerde biter.
    """
    en_kisa = max(_MERGE_MIN_STEM, len(key) - _MERGE_MAX_SUFFIX)
    for length in range(len(key) - 1, en_kisa - 1, -1):
        aday = key[:length]
        if aday in stems:
            return aday
    return None


def _merge_map(keys: Sequence[str]) -> dict[str, str]:
    """Her anahtarı temsilci gövdesine eşler.

    Anahtarlar KISADAN UZUNA taranır ve birleşenler de gövde listesine girer.
    Zincirin sebebi bu: `süreçlerin` ekini (`lerin`, 5 harf) tek adımda
    `süreç`'e bağlayamaz — ek sınırı 4 — ama araya giren `süreçler` üzerinden
    iner. Birleşen anahtarı gövde listesine almasaydık iki ekli her sözcük
    ayrı terim olarak kalırdı.
    """
    sirali = sorted(keys, key=lambda key: (len(key), key))
    temsilci: dict[str, str] = {}
    govdeler: set[str] = set()
    for key in sirali:
        hedef = _merge_target(key, govdeler)
        temsilci[key] = key if hedef is None else temsilci[hedef]
        govdeler.add(key)
    return temsilci


@dataclass(frozen=True, slots=True)
class _Tarama:
    """Tek geçişlik tarama sonucu: pasaj başına terim sayacı ve yüzey biçimleri."""

    pasajlar: list[tuple[UUID, Counter[str]]]
    yuzeyler: dict[str, Counter[str]]


def _tara(chunks: Sequence[ChunkText]) -> _Tarama:
    """Pasajları BİR KEZ tarar ve birleştirilmiş anahtarlarla sayar.

    Terimler ile kenarların aynı taramadan çıkması zorunlu: ayrı taramalar ayrı
    birleştirme haritası üretirdi ve kenar sayıları terim sayılarıyla tutmazdı.
    """
    ham: list[tuple[UUID, Counter[str]]] = []
    yuzeyler: dict[str, Counter[str]] = {}
    for chunk in chunks:
        sayac = Counter[str]()
        for key, surface in _surface_tokens(chunk.text):
            sayac[key] += 1
            yuzeyler.setdefault(key, Counter())[surface] += 1
        if sayac:
            ham.append((chunk.chunk_id, sayac))

    tum_anahtarlar = {key for _, sayac in ham for key in sayac}
    birlesim = _merge_map(list(tum_anahtarlar))

    pasajlar = [(chunk_id, _katla(sayac, birlesim)) for chunk_id, sayac in ham]
    birlesik_yuzey: dict[str, Counter[str]] = {}
    for key, sayac in yuzeyler.items():
        birlesik_yuzey.setdefault(birlesim[key], Counter()).update(sayac)
    return _Tarama(pasajlar=pasajlar, yuzeyler=birlesik_yuzey)


def _katla(sayac: Counter[str], birlesim: dict[str, str]) -> Counter[str]:
    katlanmis = Counter[str]()
    for key, adet in sayac.items():
        katlanmis[birlesim[key]] += adet
    return katlanmis


def _gosterim_bicimi(key: str, yuzeyler: Counter[str]) -> str:
    """Birleştirilen varyantlardan ekranda görünecek yazımı seçer.

    "En sık yazım" YANLIŞ cevabı verir ve bunu gerçek materyalde ölçtük:
    İşletim Sistemleri notlarında `sistemi` `sistem`'den, `tablosu`
    `tablo`'dan sık geçiyor — Türkçede çekimli biçim çoğu zaman yalın
    biçimden sıktır. Liste bu yüzden "sistemi, tablosu, durumu, uzayı" diye
    çıkıyordu; kavram listesi gibi değil, bir cümleden kesilmiş parçalar gibi.

    Doğru ölçüt köke yakınlıktır: katlanmış hâli anahtarın KENDİSİ olan yüzey
    (yani yalın biçim) varsa o kazanır. Yoksa en kısa yüzey alınır; eşitlikte
    sıklık, onda da eşitlik varsa alfabetik sıra karar verir ki çıktı
    deterministik kalsın.
    """
    adaylar = sorted(
        yuzeyler.items(),
        key=lambda item: (
            text_tr.fold(item[0]) != key,  # önce yalın biçim
            len(item[0]),  # sonra kısa olan
            -item[1],  # sonra sık olan
            item[0],
        ),
    )
    return adaylar[0][0]


def analyze(
    chunks: Sequence[ChunkText],
    *,
    max_terms: int = MAX_TERMS,
    max_edges: int = MAX_EDGES,
) -> tuple[list[ConceptTerm], list[ConceptEdge]]:
    """Pasajlardan terimleri ve aralarındaki birlikte-geçme kenarlarını çıkarır."""
    tarama = _tara(chunks)

    chunk_sayisi = Counter[str]()
    toplam_sayi = Counter[str]()
    en_iyi_pasaj: dict[str, tuple[int, UUID]] = {}
    for chunk_id, sayac in tarama.pasajlar:
        for key, adet in sayac.items():
            chunk_sayisi[key] += 1
            toplam_sayi[key] += adet
            mevcut = en_iyi_pasaj.get(key)
            if mevcut is None or adet > mevcut[0]:
                en_iyi_pasaj[key] = (adet, chunk_id)

    terimler = [
        ConceptTerm(
            key=key,
            surface=_gosterim_bicimi(key, tarama.yuzeyler[key]),
            chunk_count=adet,
            total_count=toplam_sayi[key],
            chunk_id=en_iyi_pasaj[key][1],
        )
        for key, adet in chunk_sayisi.items()
        if adet >= _MIN_CHUNK_COUNT and key not in STOPWORDS
    ]
    terimler.sort(key=lambda term: (-term.chunk_count, -term.total_count, term.key))
    terimler = terimler[:max_terms]

    secili = {term.key for term in terimler}
    kenar_sayaci = Counter[tuple[str, str]]()
    for _, sayac in tarama.pasajlar:
        pasajdakiler = sorted(key for key in sayac if key in secili)
        for left, right in combinations(pasajdakiler, 2):
            kenar_sayaci[(left, right)] += 1

    kenarlar = [
        ConceptEdge(left=left, right=right, chunk_count=adet)
        for (left, right), adet in kenar_sayaci.items()
        if adet >= _MIN_CHUNK_COUNT
    ]
    kenarlar.sort(key=lambda edge: (-edge.chunk_count, edge.left, edge.right))
    return terimler, kenarlar[:max_edges]


# ---------------------------------------------------------------------------
# Veritabanı
# ---------------------------------------------------------------------------


async def load_course_chunks(
    session: AsyncSession, course_id: UUID, *, limit: int = MAX_CHUNKS
) -> tuple[list[ChunkText], bool]:
    """Dersin işlenmiş belgelerinin pasajlarını okur.

    Yalnız `COMPLETED` belgeler: işlenmekte olan ya da başarısız bir belgenin
    yarım metni kavram listesine girerse öğrenci olmayan bir kaynağa yönlenir.
    RLS ikinci katman olarak zaten ders sınırını korur; buradaki `course_id`
    filtresi uygulama katmanının kendi kapısıdır.

    İkinci dönüş değeri "kesildi mi": sınır aşıldıysa çağıran bunu kullanıcıya
    söyler, sessizce eksik sonuç göstermez.
    """
    rows = await session.execute(
        select(Chunk.id, Chunk.text)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.course_id == course_id,
            Document.course_id == course_id,
            Document.status == DocumentStatus.COMPLETED,
        )
        .order_by(Chunk.document_id, Chunk.chunk_index)
        .limit(limit + 1)
    )
    chunks = [ChunkText(chunk_id=chunk_id, text=text) for chunk_id, text in rows.all()]
    truncated = len(chunks) > limit
    return chunks[:limit], truncated


async def build_concept_map(
    session: AsyncSession,
    course_id: UUID,
    *,
    max_terms: int = MAX_TERMS,
    max_edges: int = MAX_EDGES,
) -> ConceptMap:
    """Dersin kavram haritası. Model çağrılmaz; her şey materyalden türetilir."""
    chunks, truncated = await load_course_chunks(session, course_id)
    terms, edges = analyze(chunks, max_terms=max_terms, max_edges=max_edges)
    return ConceptMap(terms=terms, edges=edges, chunk_count=len(chunks), truncated=truncated)
