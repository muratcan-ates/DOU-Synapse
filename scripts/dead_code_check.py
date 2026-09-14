#!/usr/bin/env python3
"""Bağımlılık eklemeden, `ast` ile modül düzeyi ölü kod taraması.

Neden bir kapı gerekiyor: `.ai/agent-queue.md` A9 işi `vulture` (Python) ve `knip`
(TS) bağımlılık onayı beklediği için BLOCKED durumda. Ama ölü kodun maliyeti onay
beklemiyor: okunan ama koşmayan her fonksiyon, incelemede zaman yiyen ve "bu hâlâ
kullanılıyor mu" sorusunu her seferinde yeniden sordurtan bir yük. Python 3.12
standart kütüphanesindeki `ast`, bu değerin büyük kısmını üçüncü parti paket
olmadan üretmeye yeter; bu betik onu yapar.

Yakaladığı gerçek başarısızlık: bir dal bir yardımcı fonksiyonu yazar, sonraki dal
çağrı yerini değiştirir ya da siler, fonksiyon dosyada kalır. Hiçbir test kırılmaz
(fonksiyon zaten koşmuyordu), ruff da susar (`F401` yalnız kullanılmayan **import**
görür, kullanılmayan **tanım** değil). Sonuç, hiçbir aracın işaret etmediği ve
yalnız insan gözünün fark edebileceği bir artık.

## Neden bu tür araçlar genelde rafta kalır

Ölü kod tespiti aslında "erişilebilirlik" sorusudur ve statik olarak tam cevabı
yoktur. Framework'ler tam da bu yüzden yanlış pozitif üretir: FastAPI route
handler'ı hiçbir yerden **çağrılmaz**, dekoratörle **kaydedilir**; pydantic
doğrulayıcısı model tarafından çağrılır; pytest fixture'ını toplayıcı çağırır.
Bunları bilmeyen bir araç ilk koşuşunda onlarca sahte bulgu basar, ekip aracı
kapatır ve gerçek ölü kod da bir daha görünmez. Aracın değeri, bulduklarında
değil, **basmadıklarında**dır.

Bu yüzden aşağıdaki istisnalar gerekçeleriyle uygulanır:

1. **Dekoratörle kayıtlı fonksiyonlar** — `@router.get/post/put/patch/delete`,
   `@app.on_event`, `@app.middleware`, `@app.exception_handler`. Bunlar çağrılmaz;
   dekoratör onları bir yönlendiriciye yazar. `apps/api/app/api/health.py:20`
   (`@router.get("/live")`) bu istisna olmadan ölü görünürdü.
2. **pydantic doğrulayıcıları** — `@field_validator`, `@model_validator`,
   `@computed_field`, `@field_serializer`, `@model_serializer`. Çağıran pydantic'in
   kendisidir. `apps/api/app/core/config.py` yedi tanesini barındırıyor.
3. **pytest yüzeyi** — `conftest.py`'nin tamamı, `@pytest.fixture` ile işaretli her
   şey, `test_*` ve `pytest_*` adları, ve bir test modülündeki `Test*` **sınıfları**.
   Çağıran toplayıcıdır. Son madde ölçülerek eklendi: `apps/api/tests` rapor
   kapsamına alındığında araç 202 aday bastı, 190'ı `TestYetkilendirme`,
   `TestOnbellek` gibi pytest sınıflarıydı. pytest bu sınıfları `python_classes`
   sözleşmesiyle **adlarından** toplar, hiçbir yerden çağırmaz; sınıf adı kuralını
   bilmeyen bir araç tek bir depoda iki yüz sahte bulgu üretir.
4. **`__all__` içindeki her ad ve `__init__.py`'nin tamamı** — bunlar modülün
   dışarıya açtığı yüzeydir. Depoda kullanılmıyor olsalar bile silinmeleri
   sözleşme değişikliğidir, temizlik değil.
5. **Dunder adlar, `main`, `if __name__ == "__main__"`** — çağıran yorumlayıcı ya
   da kabuk. `scripts/*.py` dosyalarının tamamı `main` ile giriliyor.
6. **SQLAlchemy `Base` alt sınıfları** — model sınıfı çoğu zaman yalnız
   `Base.metadata` ve `relationship("Ad")` üzerinden, yani adıyla değil dizgesiyle
   kullanılır. `__tablename__` tanımlayan her sınıf da aynı sebeple muaf.
   `Mapped[...]` sütunları sınıf içi olduğu için zaten rapor yüzeyinde değil; buna
   karşılık `Mapped[uuid_pk]` gibi ek açıklamalar **referans sayılır**, böylece
   `apps/api/app/models/base.py`'deki modül düzeyi `uuid_pk`/`ts_now`/`created_at`
   takma adları ölü görünmez.
7. **`# ölü-kod: bilinçli` yorumu** — tanımın kendi satırında, dekoratör
   satırlarında ya da hemen üstündeki satırda geçerse tanım atlanır. ASCII
   yazamayan ortamlar için `# olu-kod: bilincli` de kabul edilir. Bu işaretin
   seçilme sebebi: `# noqa` gibi bir araç adına değil, **karara** atıf yapması —
   okuyan kişi "bu araç susturulmuş" değil "biri bunun kalmasına karar vermiş"
   bilgisini alır.

## Referans sayma kuralı (ve bilinçli kör noktaları)

Bir ad şu yerlerde geçiyorsa "kullanılıyor" sayılır: `Name` okuması, **nitelik
adı** (`modul.foo` → `foo`), `from x import foo` içindeki `foo`, ve tanım adına
birebir eşit her **dizge sabiti** (`relationship("Course")`, `getattr(o, "foo")`,
ileri başvurulu `"CourseAiPolicy"` ek açıklamaları).

Bu kasıtlı olarak **cömert** bir kuraldır: içe aktarma çizgesi kurulmaz, ad
çakışmaları ayrıştırılmaz. Sonucu şudur — iki modülde aynı adlı iki fonksiyon
varsa ve biri kullanılıyorsa ikisi de canlı sayılır (yanlış negatif). Takas
bilinçli: bu kapının rapor ettiği her şeyin gerçekten ölü olması, her ölüyü
bulmasından daha değerli. Rapor edilmeyen ölü kod kimseye zarar vermez; sahte
bulgu aracı çöpe attırır.

Tek istisna özyinelemedir: bir tanımın **kendi gövdesindeki** kendine referansı
sayılmaz, yoksa kendini çağıran ölü bir fonksiyon kendini diri tutardı. Karşılıklı
özyineleme (A→B, B→A, ikisi de ölü) hâlâ görünmez; bunu yakalamak içe aktarma
çizgesi gerektirir ve bu betiğin kapsamı dışındadır.

## Rapor kapsamı ile referans kapsamı aynı küme değildir

Bu ayrım bu betiğin en pahalı dersiydi. İlk gerçek koşuşunda `apps/api/app`
üzerinde 11 aday bastı; onbirinin **onu** diriydi ve `apps/api/tests/`,
`scripts/` ya da `evaluation/` içinden çağrılıyordu: test kancaları
(`set_providers`, `set_storage`, `set_embedding_provider`), yalnız bir betikten
çağrılan `provider_preflight`, yalnız testte kurulan `AnswerPipeline`. Araç
"bu adı kim kullanıyor" sorusuna yalnız **taradığı** dizinden cevap arıyordu; o
dizinin dışındaki her çağıran yokmuş gibi davranıyordu. Bu tam olarak yukarıda
anlatılan, ilk koşuşta güveni tüketip raftan inmeyen araç durumudur.

Düzeltme kavramsaldır — **nerede tanım aradığımız** ile **nerede kullanım
aradığımız** ayrılır:

* **Rapor kapsamı** — komut satırında verilen yollar. Bulgular yalnız buradan çıkar.
* **Referans kapsamı** — varsayılan olarak **deponun kökü**: verilen yollardan
  yukarı yürünerek bulunan ilk `.git` girdisi (git worktree'de `.git` bir
  *dosyadır*, o da sayılır). Kullanım burada aranır.

Böylece `dead_code_check.py apps/api/app` komutu "apps/api/app içindeki ölüleri,
**tüm deponun** kullanımına bakarak söyle" anlamına gelir — yazan kişinin zaten
kastettiği şey. Kök bulunamazsa referans kapsamı rapor kapsamına eşitlenir ve
rapor bunu satır olarak **yazar**: hiçbir kapı neye baktığını gizlememelidir.
`--reference-path` ek kök ekler, `--no-repo-references` otomatik bulmayı kapatır.

Referans kapsamındaki ayrıştırma hatası çıkış kodunu **değiştirmez** ama basılır.
Gerekçe asimetriktir: rapor kapsamındaki okunamayan dosya bir *tanımı* gizler
(kapı göremediği şey için PASS yazmamalı, bu yüzden rc=1), referans kapsamındaki
okunamayan dosya ise bir *kullanımı* gizler — yani sahte bir bulguya yol açabilir.
Okuyan kişi bunu bilmeli; ama deponun her dosyasının ayrıştırılabilir olmasını
zorlamak bu kapının işi değildir, o başka kapıların sorusudur.

## Çıkış kodu

Kuyruk A9 için "ilk hafta yalnız uyarı" diyor; **varsayılan da budur**: bulgular
basılır, çıkış kodu 0'dır. Kapıyı kırmızı yakmak açık bir karardır: `--strict`.
Tek ayrık durum ayrıştırma hatasıdır — okunamayan dosya bir bulgu değil, kapının
**kör noktası**dır; uyarı modunda bile çıkış kodu 1 olur, çünkü hiçbir kapı
göremediği şey için PASS yazmamalıdır.

Kullanım:

    python3 scripts/dead_code_check.py apps/api/app
    python3 scripts/dead_code_check.py apps/api/app scripts --strict
    python3 scripts/dead_code_check.py apps/api --ignore '*/tests/*'
    python3 scripts/dead_code_check.py apps/api/app --reference-path evaluation
    python3 scripts/dead_code_check.py apps/api/app --no-repo-references

Ağ, veritabanı ve üçüncü parti bağımlılık gerektirmez.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

# `# ölü-kod: bilinçli` işaretinin ASCII'siz yazılamadığı ortamlar için ikinci
# yazım da tanınır; iki yazımı da tek yerde tutmak, işaretin "hangi harfle
# yazmıştım" sorusuna dönüşmesini engeller.
DELIBERATE_MARKER = re.compile(r"#\s*(?:ölü|olu)-kod\s*:\s*(?:bilinçli|bilincli)")

# Dekoratörün YALNIZ son bileşeni eşleştirilir (`router.get` → `get`), çünkü
# yönlendiricinin değişken adı dosyadan dosyaya değişir (`router`, `api_router`,
# `app`). Bu kural gereğinden geniştir ve bilerek öyledir: bir dekoratör yanlışlıkla
# muaf tutulursa en kötü ihtimalle bir ölü tanım rapor edilmez.
REGISTRATION_DECORATORS = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
        "route",
        "api_route",
        "websocket",
        "on_event",
        "middleware",
        "exception_handler",
        "register",
        "listens_for",
        "setter",
        "getter",
        "deleter",
    }
)

PYDANTIC_DECORATORS = frozenset(
    {
        "field_validator",
        "model_validator",
        "computed_field",
        "field_serializer",
        "model_serializer",
        "validator",
        "root_validator",
    }
)

PYTEST_DECORATORS = frozenset({"fixture"})

TYPING_DECORATORS = frozenset({"overload", "runtime_checkable"})

ORM_BASE_NAMES = frozenset({"Base", "DeclarativeBase", "DeclarativeBaseNoMeta"})

SKIPPED_DIRECTORIES = frozenset(
    {"__pycache__", ".venv", "venv", "node_modules", ".git", ".mypy_cache", ".ruff_cache"}
)

EXEMPTION_DUNDER = "dunder / giriş noktası"
EXEMPTION_EXPORT = "__all__ ihracı"
EXEMPTION_PACKAGE = "__init__.py re-export yüzeyi"
EXEMPTION_PYTEST = "pytest yüzeyi"
EXEMPTION_REGISTERED = "dekoratörle kayıtlı"
EXEMPTION_PYDANTIC = "pydantic doğrulayıcı"
EXEMPTION_TYPING = "typing dekoratörü"
EXEMPTION_ORM = "SQLAlchemy modeli"
EXEMPTION_MARKED = "bilinçli işaret"

# pytest bir test modülündeki sınıfları `python_classes` sözleşmesiyle **adından**
# toplar (varsayılan önek `Test`). Bu sınıflar hiçbir yerden çağrılmaz; kuralı
# bilmeyen araç her test dosyasında sınıf sayısı kadar sahte bulgu üretir.
PYTEST_CLASS_PREFIX = "Test"
PYTEST_FILE_PATTERNS = ("test_*.py", "*_test.py")

KIND_FUNCTION = "fonksiyon"
KIND_CLASS = "sınıf"
KIND_CONSTANT = "sabit"

DefinitionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


@dataclass(frozen=True)
class Definition:
    """Rapor edilebilir tek bir modül düzeyi tanım."""

    name: str
    kind: str
    relative: str
    line: int
    exemption: str | None


@dataclass(frozen=True)
class FileContext:
    """Tek dosyanın, istisna kararları için gereken bağlamı.

    `records_definitions` yanlışsa dosya yalnız **referans kapsamındadır**:
    içindeki adlar kullanım sayılır ama tanımları rapora girmez.
    """

    relative: str
    is_package_init: bool
    is_conftest: bool
    is_pytest_module: bool
    exported: frozenset[str]
    marked_lines: frozenset[int]
    records_definitions: bool = True


@dataclass
class Survey:
    """Tüm taramanın ham sonucu; karar `dead_definitions` içinde verilir."""

    definitions: list[Definition] = field(default_factory=list)
    # Ad → o adı kullanan modül düzeyi tanımların adları. `None` sahibi, hiçbir
    # tanımın içinde olmayan (modül gövdesindeki) kullanımları temsil eder.
    users: dict[str, set[str | None]] = field(default_factory=lambda: defaultdict(set))
    parse_errors: list[str] = field(default_factory=list)
    scanned_files: int = 0
    # Referans kapsamı: yalnız kullanım toplanan dosyalar. Buradaki ayrıştırma
    # hatası çıkış kodunu değiştirmez (modül docstring'i, "Rapor kapsamı" bölümü).
    reference_files: int = 0
    reference_parse_errors: list[str] = field(default_factory=list)
    # Raporun "neye baktım" satırı; kullanıcıya görünür, bu yüzden Türkçe cümledir.
    reference_scope: str = ""


def iter_python_files(paths: Iterable[Path], ignores: Iterable[str]) -> Iterator[Path]:
    """Verilen yol(lar)ın altındaki `.py` dosyalarını sıralı biçimde üret."""
    patterns = list(ignores)
    seen: set[Path] = set()
    for raw in paths:
        candidates = [raw] if raw.is_file() else sorted(raw.rglob("*.py"))
        for candidate in candidates:
            if candidate.suffix != ".py" or candidate in seen:
                continue
            if any(part in SKIPPED_DIRECTORIES for part in candidate.parts):
                continue
            text = candidate.as_posix()
            if any(
                fnmatch.fnmatch(text, p) or fnmatch.fnmatch(candidate.name, p) for p in patterns
            ):
                continue
            seen.add(candidate)
            yield candidate


def decorator_tail(node: ast.expr) -> str | None:
    """Dekoratör ifadesinin son ad bileşenini döndür (`a.b.c(...)` → `c`)."""
    current = node.func if isinstance(node, ast.Call) else node
    if isinstance(current, ast.Attribute):
        return current.attr
    if isinstance(current, ast.Name):
        return current.id
    return None


def exported_names(module: ast.Module) -> frozenset[str]:
    """Modül gövdesindeki `__all__` dizge üyelerini topla."""
    names: set[str] = set()
    for node in module.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.List | ast.Tuple | ast.Set):
            for element in value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.add(element.value)
    return frozenset(names)


def marked_lines(source: str) -> frozenset[int]:
    """`# ölü-kod: bilinçli` işareti taşıyan 1 tabanlı satır numaraları."""
    return frozenset(
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if DELIBERATE_MARKER.search(line)
    )


def _record_reference(name: str, owner: str | None, survey: Survey) -> None:
    survey.users[name].add(owner)


def collect_references(node: ast.AST, owner: str | None, survey: Survey) -> None:
    """`node` alt ağacındaki her ad kullanımını `owner` sahipliğiyle kaydet.

    Nitelik adları ve kimlik biçimindeki dizge sabitleri de sayılır; gerekçesi
    modül docstring'indeki "Referans sayma kuralı" bölümündedir.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if isinstance(child.ctx, ast.Load):
                _record_reference(child.id, owner, survey)
        elif isinstance(child, ast.Attribute):
            _record_reference(child.attr, owner, survey)
        elif isinstance(child, ast.Constant):
            if isinstance(child.value, str) and child.value.isidentifier():
                _record_reference(child.value, owner, survey)
        elif isinstance(child, ast.ImportFrom):
            for alias in child.names:
                _record_reference(alias.name, owner, survey)
        elif isinstance(child, ast.Import):
            for alias in child.names:
                _record_reference(alias.name.rsplit(".", 1)[-1], owner, survey)


def collect_definition_references(node: DefinitionNode, survey: Survey) -> None:
    """Tanımın gövdesini kendi sahipliğiyle, dekoratörlerini modül sahipliğiyle tara.

    Ayrım önemlidir: dekoratör modül düzeyinde değerlendirilir, dolayısıyla
    oradaki adlar tanımın "kendi içi" sayılmaz. Gövde ise sayılır; bu sayede
    yalnız kendini çağıran ölü bir fonksiyon kendini diri tutamaz.
    """
    decorators = {id(decorator) for decorator in node.decorator_list}
    for child in ast.iter_child_nodes(node):
        collect_references(child, None if id(child) in decorators else node.name, survey)


def exemption_for_definition(node: DefinitionNode, context: FileContext) -> str | None:
    """Bir fonksiyon/sınıf tanımı için geçerli istisnayı (varsa) döndür."""
    name = node.name
    if is_marked(node.lineno, [d.lineno for d in node.decorator_list], context):
        return EXEMPTION_MARKED
    if name.startswith("__") and name.endswith("__"):
        return EXEMPTION_DUNDER
    if name == "main":
        return EXEMPTION_DUNDER
    if name in context.exported:
        return EXEMPTION_EXPORT
    if context.is_package_init:
        return EXEMPTION_PACKAGE
    if context.is_conftest or name.startswith(("test_", "pytest_")):
        return EXEMPTION_PYTEST
    if (
        context.is_pytest_module
        and isinstance(node, ast.ClassDef)
        and name.startswith(PYTEST_CLASS_PREFIX)
    ):
        return EXEMPTION_PYTEST

    tails = {tail for tail in map(decorator_tail, node.decorator_list) if tail is not None}
    if tails & PYTEST_DECORATORS:
        return EXEMPTION_PYTEST
    if tails & PYDANTIC_DECORATORS:
        return EXEMPTION_PYDANTIC
    if tails & REGISTRATION_DECORATORS:
        return EXEMPTION_REGISTERED
    if tails & TYPING_DECORATORS:
        return EXEMPTION_TYPING

    if isinstance(node, ast.ClassDef) and is_orm_model(node):
        return EXEMPTION_ORM
    return None


def is_orm_model(node: ast.ClassDef) -> bool:
    """Sınıf SQLAlchemy tablosu mu? Taban adına ya da `__tablename__`e bakılır."""
    for base in node.bases:
        tail = decorator_tail(base)
        if tail is not None and tail in ORM_BASE_NAMES:
            return True
    for statement in node.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
        if any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in targets):
            return True
    return False


def is_marked(line: int, decorator_lines: list[int], context: FileContext) -> bool:
    """İşaret, tanımın satırında, dekoratör satırlarında ya da hemen üstünde mi?"""
    first = min([line, *decorator_lines])
    return bool(context.marked_lines & set(range(first - 1, line + 1)))


def exemption_for_constant(name: str, line: int, context: FileContext) -> str | None:
    """Modül düzeyi bir sabit/atama için geçerli istisnayı (varsa) döndür."""
    if is_marked(line, [], context):
        return EXEMPTION_MARKED
    if name.startswith("__") and name.endswith("__"):
        return EXEMPTION_DUNDER
    if name in context.exported:
        return EXEMPTION_EXPORT
    if context.is_package_init:
        return EXEMPTION_PACKAGE
    if context.is_conftest:
        return EXEMPTION_PYTEST
    return None


def assigned_names(node: ast.Assign | ast.AnnAssign) -> list[tuple[str, int]]:
    """Atamanın bağladığı modül düzeyi adları (ad, satır) olarak döndür.

    Nitelik ve indeks hedefleri (`obj.x = ...`, `d["k"] = ...`) atlanır: bunlar
    yeni bir modül sembolü tanımlamaz, var olanı değiştirir.
    """
    if node.value is None:
        return []
    targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
    found: list[tuple[str, int]] = []
    for target in targets:
        elements = target.elts if isinstance(target, ast.Tuple | ast.List) else [target]
        for element in elements:
            if isinstance(element, ast.Name):
                found.append((element.id, element.lineno))
    return found


def survey_statements(statements: list[ast.stmt], context: FileContext, survey: Survey) -> None:
    """Modül düzeyi deyimleri gez; `if`/`try` gövdeleri de modül düzeyi sayılır.

    `if TYPE_CHECKING:` ve `try: import ... except ImportError:` blokları gerçek
    modül yüzeyidir; içlerindeki tanımlar da taranmalıdır.
    """
    for node in statements:
        if isinstance(node, ast.If):
            collect_references(node.test, None, survey)
            survey_statements(node.body, context, survey)
            survey_statements(node.orelse, context, survey)
        elif isinstance(node, ast.Try | ast.TryStar):
            survey_statements(node.body, context, survey)
            for handler in node.handlers:
                if handler.type is not None:
                    collect_references(handler.type, None, survey)
                survey_statements(handler.body, context, survey)
            survey_statements(node.orelse, context, survey)
            survey_statements(node.finalbody, context, survey)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            kind = KIND_CLASS if isinstance(node, ast.ClassDef) else KIND_FUNCTION
            if context.records_definitions:
                survey.definitions.append(
                    Definition(
                        name=node.name,
                        kind=kind,
                        relative=context.relative,
                        line=node.lineno,
                        exemption=exemption_for_definition(node, context),
                    )
                )
            collect_definition_references(node, survey)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            if context.records_definitions:
                for name, line in assigned_names(node):
                    survey.definitions.append(
                        Definition(
                            name=name,
                            kind=KIND_CONSTANT,
                            relative=context.relative,
                            line=line,
                            exemption=exemption_for_constant(name, line, context),
                        )
                    )
            collect_references(node, None, survey)
        else:
            collect_references(node, None, survey)


def is_pytest_module(name: str) -> bool:
    """Dosya adı pytest'in topladığı modül desenlerinden birine uyuyor mu?"""
    return any(fnmatch.fnmatch(name, pattern) for pattern in PYTEST_FILE_PATTERNS)


def survey_file(
    path: Path, root: Path, survey: Survey, *, records_definitions: bool = True
) -> None:
    """Tek dosyayı tara; okunamayan ya da ayrıştırılamayan dosyayı kör nokta say.

    `records_definitions` yanlışsa dosya yalnız referans kapsamındadır: adları
    kullanım sayılır, tanımları rapora girmez ve ayrıştırma hatası çıkış kodunu
    değiştirmez (modül docstring'i, "Rapor kapsamı" bölümü).
    """
    errors = survey.parse_errors if records_definitions else survey.reference_parse_errors
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{relative}: okunamadı ({error})")
        return
    try:
        module = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        location = f":{error.lineno}" if error.lineno else ""
        errors.append(f"{relative}{location}: ayrıştırılamadı ({error.msg})")
        return
    except (ValueError, RecursionError) as error:
        # Null bayt taşıyan ya da aşırı iç içe geçmiş kaynak `SyntaxError` değil
        # başka bir istisna atar. Kapı tek bozuk dosya yüzünden çökerse geri
        # kalan yüzeyi hiç göremez; bu yüzden burada da kör nokta olarak yazılır.
        errors.append(f"{relative}: ayrıştırılamadı ({error})")
        return

    if records_definitions:
        survey.scanned_files += 1
    else:
        survey.reference_files += 1
    context = FileContext(
        relative=relative,
        is_package_init=path.name == "__init__.py",
        is_conftest=path.name == "conftest.py",
        is_pytest_module=is_pytest_module(path.name),
        exported=exported_names(module),
        marked_lines=marked_lines(source),
        records_definitions=records_definitions,
    )
    survey_statements(module.body, context, survey)


def find_repository_root(paths: Iterable[Path]) -> Path | None:
    """Verilen yollardan yukarı yürüyerek ilk `.git` girdisini taşıyan dizini bul.

    Git worktree'de `.git` bir *dosyadır*; `exists()` ikisini de gördüğü için
    ayrı bir dal gerekmez. Bulunamazsa `None` döner ve çağıran referans
    kapsamını rapor kapsamına eşitler — sessizce değil, raporda yazarak.
    """
    for path in paths:
        current = path.resolve()
        if current.is_file():
            current = current.parent
        for candidate in [current, *current.parents]:
            if (candidate / ".git").exists():
                return candidate
    return None


def survey_paths(
    paths: Iterable[Path],
    ignores: Iterable[str],
    root: Path,
    reference_roots: Iterable[Path] = (),
) -> Survey:
    """Rapor kapsamını tara, sonra referans kapsamından yalnız kullanımları topla."""
    survey = Survey()
    visited: set[Path] = set()
    for path in iter_python_files(paths, ignores):
        visited.add(path.resolve())
        survey_file(path, root, survey)
    for path in iter_python_files(reference_roots, ignores):
        resolved = path.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        survey_file(path, root, survey, records_definitions=False)
    return survey


def dead_definitions(survey: Survey) -> list[Definition]:
    """Muaf olmayan ve hiçbir yerden referans verilmeyen tanımları sırayla döndür.

    "Referans verilmiş" demek, adı kullanan en az bir sahibin tanımın KENDİSİ
    olmaması demektir; tanımın kendi gövdesindeki kendine atıf sayılmaz.
    """
    dead = [
        definition
        for definition in survey.definitions
        if definition.exemption is None
        and not (survey.users.get(definition.name, set()) - {definition.name})
    ]
    return sorted(dead, key=lambda d: (d.relative, d.line, d.name))


def format_report(survey: Survey, dead: list[Definition], strict: bool) -> list[str]:
    """Kapının stdout çıktısını satır satır kur."""
    lines: list[str] = []
    exempt = Counter(d.exemption for d in survey.definitions if d.exemption is not None)
    checked = len(survey.definitions) - sum(exempt.values())

    if survey.parse_errors:
        status = "FAIL"
    elif not dead:
        status = "PASS"
    else:
        status = "FAIL" if strict else "WARN"

    lines.append(
        f"DEAD_CODE_CHECK={status} "
        f"({survey.scanned_files} dosya, {len(survey.definitions)} tanım, "
        f"{checked} denetlendi, {sum(exempt.values())} muaf, {len(dead)} aday)"
    )
    for error in survey.parse_errors:
        lines.append(f"  ! ayrıştırma: {error}")
    for definition in dead:
        lines.append(
            f"  - {definition.relative}:{definition.line} "
            f"{definition.kind} `{definition.name}` — hiçbir yerden referans yok"
        )
    if exempt:
        detail = ", ".join(f"{reason}={count}" for reason, count in sorted(exempt.items()))
        lines.append(f"  muafiyet: {detail}")
    if survey.reference_scope:
        lines.append(
            f"  referans kapsamı: {survey.reference_scope} "
            f"({survey.reference_files} ek dosyada kullanım arandı)"
        )
    for error in survey.reference_parse_errors:
        lines.append(f"  ~ referans ayrıştırma: {error} (çıkış kodunu değiştirmez)")
    if dead and not strict:
        lines.append("  (uyarı modu: çıkış kodu 0. Kapıyı kırmızı yakmak için --strict.)")
    if survey.parse_errors:
        lines.append("  (ayrıştırılamayan dosya kapının kör noktasıdır; uyarı modunda da rc=1.)")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Taranacak dosya ya da dizin(ler), örn. apps/api/app",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="DESEN",
        help="Atlanacak yol deseni (fnmatch; yola ve dosya adına uygulanır). Tekrarlanabilir.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Raporda göreli yolların ölçüleceği kök (varsayılan: çalışma dizini).",
    )
    parser.add_argument(
        "--reference-path",
        action="append",
        default=[],
        type=Path,
        metavar="YOL",
        help="Kullanım aranacak ek kök (tanım toplanmaz). Tekrarlanabilir.",
    )
    parser.add_argument(
        "--no-repo-references",
        action="store_true",
        help="Depo kökünü referans kapsamına otomatik ekleme; yalnız verilen yollara bak.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--warn-only",
        action="store_true",
        help="Bulguları bas ama çıkış kodu 0 kalsın (VARSAYILAN; açıkça yazılabilir).",
    )
    mode.add_argument(
        "--strict",
        action="store_true",
        help="Bulgu varsa çıkış kodu 1 olsun.",
    )
    arguments = parser.parse_args(argv)

    missing = [
        str(path) for path in [*arguments.paths, *arguments.reference_path] if not path.exists()
    ]
    if missing:
        print("DEAD_CODE_CHECK=FAIL")
        for path in missing:
            print(f"  ! yol yok: {path}")
        return 1

    reference_roots = list(arguments.reference_path)
    scope_notes = [str(path) for path in arguments.reference_path]
    if arguments.no_repo_references:
        scope_notes.append("depo kökü kapalı (--no-repo-references)")
    else:
        repository_root = find_repository_root(arguments.paths)
        if repository_root is None:
            scope_notes.append("depo kökü bulunamadı, yalnız rapor kapsamına bakıldı")
        else:
            reference_roots.append(repository_root)
            scope_notes.append(f"depo kökü {repository_root}")

    survey = survey_paths(
        arguments.paths, arguments.ignore, arguments.root.resolve(), reference_roots
    )
    survey.reference_scope = "; ".join(scope_notes)
    if survey.scanned_files == 0 and not survey.parse_errors:
        print("DEAD_CODE_CHECK=FAIL")
        print("  ! taranacak .py dosyası bulunamadı — kapı boş küme üzerinde PASS yazmaz.")
        return 1

    dead = dead_definitions(survey)
    for line in format_report(survey, dead, arguments.strict):
        print(line)

    if survey.parse_errors:
        return 1
    if dead and arguments.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
