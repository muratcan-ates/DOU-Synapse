"""Gold set yükleme, doğrulama ve kaynak eşleme — tek kaynak.

Neden ayrı modül: `evaluate.py` (ölçüm koşusu) ve `verify_gold_set.py` (denetim)
aynı kuralları uygular. İki yerde ayrı ayrı yazılsalardı zamanla ayrışırlardı ve
ayrışma sessiz olurdu — biri "expected_sources boş olabilir" derken diğeri
diyemez hale gelirdi (Anayasa XI).

Bu dosya bilinçli olarak BAĞIMSIZDIR: veritabanı, SQLAlchemy veya `app` paketi
import etmez. Böylece gold set denetimi Postgres olmadan da koşar ve CI'da
ucuzdur.

Kalıcı kimlik kuralı (brief §Teslimat 3): gold set'te chunk UUID'si TUTULMAZ.
`chunks.id` her ingest'te `gen_random_uuid()` ile yeniden üretilir; elle yazılan
bir UUID bir sonraki yüklemede sessizce kopar ve bunu ancak metrikler sıfırlanınca
fark edersin. Kalıcı kimlik `(file_name, page_number | slide_number | section_title)`
üçlüsüdür ve chunk id'leri koşu anında çözülür.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# `expected_behavior` alanının kapalı değer kümesi. Yeni değer eklemek raporun
# metrik tanımını da değiştirir; bu yüzden burada sabittir ve doğrulanır.
BEHAVIORS = frozenset(
    {"answered", "insufficient_context", "out_of_scope", "ignore_injection", "no_leak"}
)

# Reddedilmesi BEKLENEN davranışlar: ret F1'in pozitif sınıfı (brief §Metrik tanımları).
REFUSAL_BEHAVIORS = frozenset({"insufficient_context", "out_of_scope"})

# Retrieval metrikleri yalnız "cevaplanabilir" kategorilerde anlamlıdır: kapsam dışı
# bir sorunun beklenen kaynağı yoktur, Recall'a katılırsa metriği yapay olarak düşürür.
RETRIEVAL_CATEGORIES = frozenset({"direct", "multi_chunk", "technical_term", "code_review"})

_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_WHITESPACE = re.compile(r"\s+")


class GoldSetError(Exception):
    """Gold set yapısal olarak bozuk — koşu başlatılmaz (fail-closed)."""


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Beklenen tek kaynak. UUID YOK; kalıcı kimlik burada.

    Daraltma alanlarının hiçbiri verilmezse eşleşme dosya düzeyindedir: o dosyanın
    herhangi bir chunk'ı isabet sayılır. Kod dosyalarında bilinçli tercih budur —
    kod chunk'larının `section_title`'ı chunking birleştirmesiyle kayabilir
    (chunking.py, küçük blok birleştirme), sayfa numarası ise hiç yoktur.
    """

    file_name: str
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None
    #: Chunk metninde birebir geçmesi beklenen çapa metin (opsiyonel daraltma).
    text_contains: str | None = None

    def matches(
        self,
        *,
        file_name: str,
        page_number: int | None,
        slide_number: int | None,
        section_title: str | None,
        text: str,
    ) -> bool:
        if file_name != self.file_name:
            return False
        if self.page_number is not None and page_number != self.page_number:
            return False
        if self.slide_number is not None and slide_number != self.slide_number:
            return False
        if self.section_title is not None and section_title != self.section_title:
            return False
        return not (self.text_contains is not None and self.text_contains not in text)

    def label(self) -> str:
        if self.page_number is not None:
            return f"{self.file_name}#s{self.page_number}"
        if self.slide_number is not None:
            return f"{self.file_name}#slayt{self.slide_number}"
        if self.section_title is not None:
            return f"{self.file_name}#{self.section_title}"
        return self.file_name


@dataclass(frozen=True, slots=True)
class GoldItem:
    id: str
    question: str
    category: str
    expected_behavior: str
    expected_sources: tuple[SourceSpec, ...] = ()
    notes: str | None = None
    question_type: str | None = None
    pattern_family: str | None = None
    leak_vector: str | None = None
    r2_case_ref: str | None = None

    @property
    def is_retrieval_scored(self) -> bool:
        """Recall/MRR bu soruda ölçülür mü?"""
        return self.category in RETRIEVAL_CATEGORIES and bool(self.expected_sources)

    @property
    def should_refuse(self) -> bool:
        return self.expected_behavior in REFUSAL_BEHAVIORS


@dataclass(frozen=True, slots=True)
class GoldSet:
    name: str
    version: str
    material: str
    items: tuple[GoldItem, ...]
    path: Path
    #: Dosyanın ham metni — UUID taraması bunun üzerinde koşar (aşağıdaki gerekçe).
    raw_text: str = ""
    category_targets: dict[str, int] = field(default_factory=dict)

    def by_category(self) -> Counter[str]:
        return Counter(item.category for item in self.items)

    def scored_items(self) -> tuple[GoldItem, ...]:
        return tuple(item for item in self.items if item.is_retrieval_scored)


def normalize_question(text: str) -> str:
    """Kesişim kontrolü için soru metnini normalize eder.

    Yalnız büyük/küçük harf ve boşluk farkını siler. Türkçe'de `casefold()`
    kullanılır: `lower()` ile 'I' -> 'i' dönüşümü noktalı/noktasız ayrımını bozar ve
    iki farklı soruyu aynı sayabilir.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", folded).strip()


def _parse_source(raw: Any, item_id: str) -> SourceSpec:
    if not isinstance(raw, dict):
        raise GoldSetError(f"{item_id}: expected_sources girdisi nesne olmalı, {type(raw)} geldi.")
    unknown = set(raw) - {
        "file_name",
        "page_number",
        "slide_number",
        "section_title",
        "text_contains",
    }
    if unknown:
        raise GoldSetError(f"{item_id}: expected_sources içinde tanınmayan alan: {sorted(unknown)}")
    file_name = raw.get("file_name")
    if not isinstance(file_name, str) or not file_name:
        raise GoldSetError(f"{item_id}: expected_sources girdisinde file_name zorunlu.")
    return SourceSpec(
        file_name=file_name,
        page_number=raw.get("page_number"),
        slide_number=raw.get("slide_number"),
        section_title=raw.get("section_title"),
        text_contains=raw.get("text_contains"),
    )


def load(path: str | Path) -> GoldSet:
    """Gold set dosyasını okur ve tiplere çevirir. Yapısal hata = istisna."""
    path = Path(path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GoldSetError(f"Gold set dosyası yok: {path}") from exc
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GoldSetError(f"{path}: JSON ayrıştırılamadı — {exc}") from exc

    items: list[GoldItem] = []
    for entry in raw.get("items", []):
        item_id = entry.get("id", "<id yok>")
        for required in ("id", "question", "category", "expected_behavior"):
            if not entry.get(required):
                raise GoldSetError(f"{item_id}: '{required}' alanı zorunlu ve boş olamaz.")
        behavior = entry["expected_behavior"]
        if behavior not in BEHAVIORS:
            raise GoldSetError(
                f"{item_id}: expected_behavior '{behavior}' tanınmıyor. "
                f"İzin verilenler: {sorted(BEHAVIORS)}"
            )
        sources = tuple(_parse_source(s, item_id) for s in entry.get("expected_sources", []))
        items.append(
            GoldItem(
                id=entry["id"],
                question=entry["question"],
                category=entry["category"],
                expected_behavior=behavior,
                expected_sources=sources,
                notes=entry.get("notes"),
                question_type=entry.get("question_type"),
                pattern_family=entry.get("pattern_family"),
                leak_vector=entry.get("leak_vector"),
                r2_case_ref=entry.get("r2_case_ref"),
            )
        )

    return GoldSet(
        name=raw.get("set", path.stem),
        version=raw.get("version", "0"),
        material=raw.get("material", "bilinmiyor"),
        items=tuple(items),
        path=path,
        raw_text=raw_text,
        category_targets=raw.get("category_targets", {}),
    )


def structural_errors(gold: GoldSet) -> list[str]:
    """Veritabanı gerektirmeyen denetimler. Boş liste = temiz."""
    errors: list[str] = []

    # Gold set'e UUID yazma yasağı (brief §Teslimat 3) makineyle zorlanır. Tarama ham
    # metin üzerindedir çünkü UUID `expected_chunk_ids` gibi tipli modele hiç girmeyen
    # bir alanda da durabilir; orada dururken de aynı tuzağı kurar.
    for found in dict.fromkeys(_UUID_RE.findall(gold.raw_text)):
        errors.append(
            f"{gold.path.name}: dosyada elle yazılmış chunk UUID'si var ({found}). "
            "Kalıcı kimlik (file_name, page_number|slide_number) kullanılmalı."
        )

    seen_ids: set[str] = set()
    seen_questions: dict[str, str] = {}
    for item in gold.items:
        if item.id in seen_ids:
            errors.append(f"{item.id}: id tekrar ediyor.")
        seen_ids.add(item.id)

        key = normalize_question(item.question)
        if key in seen_questions:
            errors.append(f"{item.id}: soru metni {seen_questions[key]} ile birebir aynı.")
        else:
            seen_questions[key] = item.id

        if item.expected_behavior == "answered" and not item.expected_sources:
            errors.append(f"{item.id}: 'answered' bekleniyor ama expected_sources boş.")
        if item.expected_behavior != "answered" and item.expected_sources:
            errors.append(
                f"{item.id}: '{item.expected_behavior}' bekleniyor ama expected_sources dolu — "
                "reddedilmesi beklenen bir sorunun beklenen kaynağı olmaz."
            )
        if item.category == "code_review" and item.question_type not in {"code_trace", "bug_hunt"}:
            errors.append(f"{item.id}: code_review kaydında question_type code_trace|bug_hunt olmalı.")
        if item.category == "injection" and not item.pattern_family:
            errors.append(f"{item.id}: injection kaydında pattern_family zorunlu (kalıp ailesi).")
        if item.category == "socratic_leak" and not item.leak_vector:
            errors.append(f"{item.id}: socratic_leak kaydında leak_vector zorunlu.")

    counts = gold.by_category()
    for category, target in gold.category_targets.items():
        if counts[category] < target:
            errors.append(
                f"kategori '{category}': {counts[category]} kayıt var, hedef {target} "
                f"({target - counts[category]} eksik)."
            )

    return errors


def overlap_errors(a: GoldSet, b: GoldSet) -> list[str]:
    """Kalibrasyon ve holdout kesişimi. Kesişim = ölçüm bölümünün tamamı geçersiz.

    Jüri karşısında tek cümleyle çürütülme senaryosu budur ("yani eşiği test
    setinde ayarladınız"), o yüzden kontrol her koşudan önce koşar.
    """
    errors: list[str] = []
    a_ids = {item.id for item in a.items}
    shared_ids = a_ids & {item.id for item in b.items}
    if shared_ids:
        errors.append(f"{a.name}/{b.name} ortak id: {sorted(shared_ids)}")

    a_questions = {normalize_question(item.question): item.id for item in a.items}
    for item in b.items:
        key = normalize_question(item.question)
        if key in a_questions:
            errors.append(
                f"{a.name}/{b.name} ortak soru metni: {a_questions[key]} ↔ {item.id}"
            )
    return errors
