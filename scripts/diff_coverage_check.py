#!/usr/bin/env python3
"""Değişen satır kapsamı kapısı — `pytest-cov` ve `diff-cover` OLMADAN.

Neden bu dosya var: `.ai/agent-queue.md` A8' işi "onaydan sonra
`diff-cover coverage.xml --fail-under=85 --compare-branch=...`" diyor ve BLOCKED
duruyor, çünkü `pytest-cov` ile `diff-cover` onaylanmamış bağımlılıklar; bu depoda
`pyproject.toml`/`uv.lock` dokunulmaz. L8 şeridinin varlık nedeni tam bu: aynı
değeri **bağımlılıksız** üretmek. Python 3.12'de PEP 669 (`sys.monitoring`)
standart kütüphanededir ve satır olaylarını, coverage.py'nin 7.x'te kullandığı
mekanizmanın aynısıyla verir. Yani burada eksik olan şey kütüphane değil, yalnız
onaydı.

## Neden `sys.monitoring`, neden `sys.settrace` değil

`sys.settrace` her çerçeve için Python seviyesinde bir geri çağrı kurar ve o
çerçeve boyunca **her satırda** yeniden çağrılır; maliyeti test süitini 2–3 kat
yavaşlatacak düzeydedir ve `pytest-asyncio`/`greenlet` gibi çerçeve değiştiren
kodla birlikte kırılgandır (aynı anda tek bir izleyici olabilir, bir hata
ayıklayıcı da açıksa biri diğerini sessizce ezer).

`sys.monitoring` üç şeyi birden çözüyor:

1. **Araç kimliği** — `use_tool_id()` ile 0–5 arası bir yuva *rezerve edilir*.
   Başka bir araç (hata ayıklayıcı, profilleyici) aynı anda kendi yuvasında
   koşabilir; kimse kimseyi ezmez. Yuva doluysa `ValueError` gelir ve biz
   sessizce başka yuvaya geçeriz — sessiz veri kaybı yerine açık davranış.
2. **Yerel devre dışı bırakma** — geri çağrı `sys.monitoring.DISABLE` döndürünce
   CPython **o komut konumu için** olayı kalıcı olarak kapatır. Kapsam ölçümünde
   bir satırın *en az bir kez* koştuğunu bilmek yeter; ikinci, bininci çalışması
   yeni bilgi taşımaz. Böylece ilk isabetten sonra maliyet sıfıra iner: sıcak
   döngüler ölçülmemiş gibi hızlı koşar. `settrace` bunu yapamaz.
3. **Ölçüt eşliği** — payda için kullandığımız "çalıştırılabilir satır" kümesini
   derlenmiş kod nesnelerinin `co_lines()` çıktısından üretiyoruz; bu tam olarak
   yorumlayıcının LINE olayı üretebildiği satır kümesidir. Pay ve payda aynı
   mekanizmadan gelir, dolayısıyla "bu satır ölçülemezdi ama yine de eksik
   sayıldı" türü haksız kırmızı oluşmaz.

## İki parça

**Toplayıcı** (`LineCollector` + `pytest_configure`/`pytest_unconfigure`): bu
modül aynı zamanda bir pytest eklentisidir. `apps/api/tests/conftest.py`
DEĞİŞTİRİLMEZ; eklenti `-p scripts.diff_coverage_check` ile yüklenir ve yalnız
`DIFF_COVERAGE_OUTPUT` ortam değişkeni doluysa uyanır. Böylece modül kütüphane
olarak içe aktarıldığında (kendi testlerinde) hiçbir yan etkisi olmaz.

**Karşılaştırıcı** (`report` alt komutu): `git diff --unified=0 <base>...<head>`
çıktısını ayrıştırır, **yeni dosyadaki eklenen/değişen** satır numaralarını
çıkarır, kapsam JSON'u ile keser ve yüzde verir.

## Doğru ele alınan kenar durumları

- **Silinen dosyalar.** Silme yamasında `+++ /dev/null` yazar; o dosya bölümü ve
  onu izleyen bütün parçalar atlanır. Silinen dosyanın çalışma ağacında karşılığı
  yoktur; onu açmaya çalışmak `FileNotFoundError` ile çökmek demekti.
- **Yeniden adlandırmalar.** Git, adı değişen dosyayı `rename from`/`rename to`
  başlığıyla yazar ve değişiklik varsa `+++ b/yeni_ad` satırı gelir; satır
  numaraları doğal olarak **yeni** ada bağlanır. Saf yeniden adlandırmada (%100
  benzerlik) hiç parça yoktur, dolayısıyla eklenecek satır da yoktur — çökme yok,
  sahte satır yok.
- **Yalnız yorum/boş satır değişiklikleri paydadan düşer.** Bir yorum satırı
  `co_lines()` içinde geçmez; asla LINE olayı üretemez. Paydaya katılsaydı, "yorum
  ekledim, kapsam yüzdem düştü" gibi düzeltilmesi imkânsız bir kırmızı doğardı.
  Bu yüzden payda "değişen satırlar" değil, "değişen **ve çalıştırılabilir**
  satırlar"dır.
- **Test dosyalarının kendisi varsayılan olarak hariçtir.** Testler kendi
  kendilerini kapsar; süite dahil edilirlerse yüzde her zaman şişer ve kapı
  ölçtüğünü sandığı şeyi ölçmez. `--include-tests` ile bilinçli olarak açılır.
- **Hiç değişen satır yoksa 0/0 → yüzde HESAPLANMAZ.** 0/0'ı %100 saymak bu tür
  araçların klasik yalancı-yeşilidir: belge değişikliği içeren bir PR "kapsam
  %100" der ve eşik kapısı hiçbir şey kanıtlamadan yeşil yanar. Burada bunun
  yerine "kapsanacak satır yok" denir, yüzde basılmaz, çıkış kodu 0'dır — ve bu
  davranış testle kilitlenmiştir.
- **Python olmayan dosyalar** (`.ts`, `.sql`, `.md`) ölçülemez; paydaya girmez,
  raporun "atlandı" bölümünde nedeniyle görünür — sessizce kaybolmaz.

## Bilinçli olarak KONMAYAN şey: varsayılan eşik

`--fail-under` vardır ama **varsayılanı yoktur**. Eşik verilmezse rapor basılır ve
çıkış kodu 0 olur. Gerekçe: A8' zaten "onaydan sonra" diyor; hangi yüzdenin kapı
olacağı bir insan kararıdır ve bu şerit o kararı veremez. Sayının kendisi burada,
eşiği koyacak kişi bekleniyor.

## Ölçüm çalışma ağacına göre yapılır

Çalıştırılabilir satır kümesi, diskteki dosyadan derlenerek çıkarılır — çünkü
toplayıcı da tam olarak o dosyayı koşturmuştur. `--head` başka bir revizyona
işaret ediyorsa ya da çalışma ağacı kirliyse satır numaraları kayabilir; bu
durumda araç sayıları yine üretir ama anlamlı olmaz. Kapı, testlerin koştuğu
ağaçla aynı ağaçta koşturulmalıdır.

## Kullanım

    # 1) Kapsam topla (pytest'i eklentiyle koşturur)
    python3 scripts/diff_coverage_check.py collect --output /tmp/cov.json \
        -- tests/test_pagination.py

    # 2) Değişen satırlarla kes
    python3 scripts/diff_coverage_check.py report --coverage /tmp/cov.json --base origin/main
    python3 scripts/diff_coverage_check.py report --coverage /tmp/cov.json \
        --base origin/main --fail-under 85

Çıkış kodları: 0 temiz (ya da eşik verilmedi), 1 eşik altında, 2 aracın kendisi
ölçüm yapamadı (bozuk kapsam dosyası, git komutu düştü). 1 ile 2 bilerek
ayrılmıştır: birincisi kodun, ikincisi kurulumun sorunudur.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "dou-synapse-diff-coverage/1"
OUTPUT_ENV = "DIFF_COVERAGE_OUTPUT"
ROOT_ENV = "DIFF_COVERAGE_ROOT"
PLUGIN_NAME = "scripts.diff_coverage_check"
MARKER = "DIFF_COVERAGE_CHECK"

EXIT_CLEAN = 0
EXIT_BELOW_THRESHOLD = 1
EXIT_UNUSABLE = 2

# Yol parçası olarak görüldüğünde dosyayı ölçümün dışında bırakan işaretler.
# Bağımlılık kodu bizim kapımızın konusu değil; JSON'u da gereksiz şişirir.
FOREIGN_MARKERS = (".venv", "site-packages", "node_modules", ".tox", "__pycache__")

# Test yüzeyi: adı da klasörü de sayılır, çünkü bu depoda ikisi de kullanılıyor
# (`apps/api/tests/test_x.py` ve `scripts/test_x.py`).
TEST_BASENAME_PATTERNS = ("test_*.py", "*_test.py", "conftest.py")
TEST_DIRECTORY_NAMES = ("tests", "test")


class DiffCoverageError(RuntimeError):
    """Araç ölçüm yapamadı — sonucun kendisi değil, kurulum bozuk.

    Bu ayrım kasıtlı: eşiğin altında kalmak (çıkış 1) kodun sorunudur ve insan
    müdahalesi ister; bozuk kapsam dosyası ya da düşen `git` komutu (çıkış 2)
    kapının hiçbir şey ölçemediği anlamına gelir. İkisi aynı koda düşseydi,
    çalışmayan bir kapı "kod kötü" diye okunurdu.
    """


# --------------------------------------------------------------------------
# 1. Toplayıcı — `sys.monitoring` ile satır olayları
# --------------------------------------------------------------------------


def _acquire_tool_id() -> int:
    """Boş bir `sys.monitoring` araç yuvası rezerve eder.

    Önce `COVERAGE_ID` denenir (bu işin resmî yuvası). Doluysa — örneğin ortamda
    başka bir kapsam aracı koşuyorsa — kalan yuvalar sırayla denenir. Hiçbiri
    boş değilse sessizce ölçmemek yerine açıkça hata veririz; sessiz sürüm,
    sonradan "kapsam %0 çıktı" diye okunurdu.
    """
    monitoring = sys.monitoring
    candidates = [monitoring.COVERAGE_ID, 3, 4, monitoring.PROFILER_ID, monitoring.DEBUGGER_ID]
    for candidate in candidates:
        try:
            monitoring.use_tool_id(candidate, "dou-synapse-diff-coverage")
        except ValueError:
            continue
        return candidate
    raise DiffCoverageError(
        "sys.monitoring araç yuvalarının hepsi dolu; başka bir izleyici koşuyor olabilir"
    )


class LineCollector:
    """pytest koşarken çalıştırılan satırları toplar.

    Tasarım kararı: geri çağrı her zaman `sys.monitoring.DISABLE` döndürür. Kapsam
    için "bu satır en az bir kez koştu mu" sorusunun cevabı yeter; ilk isabetten
    sonra CPython o komut konumu için olayı kapatır ve sıcak döngüler ölçüm
    maliyetini taşımaz. Reddedilen dosyalar için de DISABLE döndürülür — bağımlılık
    kodu ilk satırından sonra bir daha hiç olay üretmez.

    Dosya kararları `_verdicts` içinde `co_filename` dizgesine göre önbelleğe
    alınır; aksi hâlde her satır olayı bir `Path.resolve()` çağrısı yapardı ve
    `sys.monitoring`'in ucuzluğu boşa giderdi.
    """

    def __init__(self, root: Path, destination: Path | None = None) -> None:
        self.root = root
        self.destination = destination
        self.files: dict[str, set[int]] = {}
        self._verdicts: dict[str, str | None] = {}
        self._tool_id: int | None = None

    def _classify(self, filename: str) -> str | None:
        """`co_filename` için depo göreli posix yolu döndürür; ölçülmeyecekse None."""
        if not filename or filename.startswith("<"):
            return None
        if not filename.endswith(".py"):
            return None
        try:
            resolved = Path(filename).resolve()
            relative = resolved.relative_to(self.root)
        except (OSError, ValueError):
            return None
        parts = relative.parts
        if any(marker in parts for marker in FOREIGN_MARKERS):
            return None
        return relative.as_posix()

    def _on_line(self, code: CodeType, line_number: int) -> object:
        filename = code.co_filename
        try:
            verdict = self._verdicts[filename]
        except KeyError:
            verdict = self._classify(filename)
            self._verdicts[filename] = verdict
        if verdict is not None:
            self.files.setdefault(verdict, set()).add(line_number)
        return sys.monitoring.DISABLE

    def start(self) -> None:
        monitoring = sys.monitoring
        self._tool_id = _acquire_tool_id()
        monitoring.register_callback(self._tool_id, monitoring.events.LINE, self._on_line)
        monitoring.set_events(self._tool_id, monitoring.events.LINE)

    def stop(self) -> None:
        """Olayları kapatır ve yuvayı iade eder; iki kez çağrılabilir."""
        if self._tool_id is None:
            return
        monitoring = sys.monitoring
        monitoring.set_events(self._tool_id, 0)
        monitoring.register_callback(self._tool_id, monitoring.events.LINE, None)
        monitoring.free_tool_id(self._tool_id)
        self._tool_id = None

    def payload(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "root": str(self.root),
            "mechanism": "sys.monitoring",
            "files": {path: sorted(lines) for path, lines in sorted(self.files.items())},
        }

    def write(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.payload(), indent=2, ensure_ascii=False, sort_keys=False)
        destination.write_text(text + "\n", encoding="utf-8")


# pytest eklentisi olarak yüklendiğinde (`-p scripts.diff_coverage_check`) kullanılır.
_ACTIVE_COLLECTOR: LineCollector | None = None


def pytest_configure(config: object) -> None:
    """Yalnız `DIFF_COVERAGE_OUTPUT` doluysa toplamaya başlar.

    Ortam değişkeni kapısı bilerek: modül kendi birim testlerinde sıradan bir
    kütüphane olarak içe aktarılıyor ve o sırada hiçbir izleyici kurulmamalı.
    """
    global _ACTIVE_COLLECTOR
    destination = os.environ.get(OUTPUT_ENV)
    if not destination or _ACTIVE_COLLECTOR is not None:
        return
    root = Path(os.environ.get(ROOT_ENV) or REPO_ROOT).resolve()
    collector = LineCollector(root, Path(destination).resolve())
    collector.start()
    _ACTIVE_COLLECTOR = collector


def pytest_unconfigure(config: object) -> None:
    """Ölçümü durdurur ve JSON'u yazar; pytest çökse de yazılır."""
    global _ACTIVE_COLLECTOR
    collector = _ACTIVE_COLLECTOR
    if collector is None:
        return
    _ACTIVE_COLLECTOR = None
    collector.stop()
    if collector.destination is not None:
        collector.write(collector.destination)


# --------------------------------------------------------------------------
# 2. Çalıştırılabilir satırlar — paydanın kaynağı
# --------------------------------------------------------------------------


def executable_lines(path: Path) -> set[int]:
    """Dosyanın LINE olayı üretebilen satır numaralarını döndürür.

    Kaynak derlenir ve bütün iç kod nesneleri (fonksiyon, sınıf, comprehension,
    lambda) gezilerek `co_lines()` birleştirilir. Bu küme tam olarak
    toplayıcının görebileceği satırlardır: yorumlar, boş satırlar ve salt
    devam eden parantez satırları burada yoktur. Payda ile payı aynı kaynaktan
    türetmek, "ölçülemeyen satır eksik sayıldı" haksızlığını kapatır.
    """
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    lines: set[int] = set()
    stack: list[CodeType] = [code]
    while stack:
        current = stack.pop()
        for _start, _end, line_number in current.co_lines():
            if line_number:
                lines.add(line_number)
        for constant in current.co_consts:
            if isinstance(constant, CodeType):
                stack.append(constant)
    return lines


# --------------------------------------------------------------------------
# 3. Diff ayrıştırma
# --------------------------------------------------------------------------

_C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, "\\": 92, '"': 34}


def _unquote_git_path(value: str) -> str:
    """Git'in C tarzı tırnakladığı yolu çözer (`"b/t\\303\\274rk.py"`).

    Git, içinde kontrol karakteri, tırnak veya ters bölü olan yolları tırnak
    içinde ve sekizlik kaçışlarla yazar. Çözmezsek yol kapsam JSON'undaki
    anahtarla eşleşmez ve dosya sessizce "kapsanmamış" görünür.
    """
    raw = value[1:-1]
    out = bytearray()
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(raw):
            break
        following = raw[index]
        if following in _C_ESCAPES:
            out.append(_C_ESCAPES[following])
            index += 1
        elif following.isdigit():
            out.append(int(raw[index : index + 3], 8))
            index += 3
        else:
            out.extend(following.encode("utf-8"))
            index += 1
    return out.decode("utf-8", errors="replace")


def _strip_diff_prefix(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = _unquote_git_path(value)
    for prefix in ("a/", "b/"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def _parse_hunk_header(line: str) -> tuple[int, int] | None:
    """`@@ -12,0 +13,3 @@` başlığından (başlangıç, adet) çıkarır.

    `--unified=0` ile bağlam satırı olmadığı için `+13,3` doğrudan "13, 14, 15
    eklendi/değişti" demektir. Adet yazılmamışsa 1'dir (git'in kısaltması);
    adet 0 ise yalnız silme olmuştur ve yeni dosyada işaretlenecek satır yoktur.
    """
    if not line.startswith("@@"):
        return None
    closing = line.find("@@", 2)
    if closing == -1:
        return None
    fields = line[2:closing].split()
    target = next((field for field in fields if field.startswith("+")), None)
    if target is None:
        return None
    body = target[1:]
    start_text, _, count_text = body.partition(",")
    try:
        start = int(start_text)
        count = 1 if count_text == "" else int(count_text)
    except ValueError:
        return None
    return start, count


def parse_unified_diff(text: str) -> dict[str, set[int]]:
    """`git diff --unified=0` çıktısından yeni dosyadaki değişen satırları çıkarır.

    Dosya başlığı `+++ /dev/null` ise dosya silinmiştir; o bölümün bütün
    parçaları atlanır. `+++ b/yeni_ad` yeniden adlandırmada da doğru adı verir,
    çünkü git satır numaralarını her zaman hedef dosyaya göre yazar.
    """
    changed: dict[str, set[int]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("+++ "):
            target = line[4:]
            current = None if target.strip() == "/dev/null" else _strip_diff_prefix(target)
        elif line.startswith("@@"):
            if current is None:
                continue
            parsed = _parse_hunk_header(line)
            if parsed is None:
                continue
            start, count = parsed
            if count > 0:
                changed.setdefault(current, set()).update(range(start, start + count))
    return changed


def _git(root: Path, *args: str) -> str:
    # shell=False ve argümanlar sabit; kullanıcı girdisi yalnız revizyon adı olarak geçer.
    completed = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        reason = detail[-1] if detail else "sebep bildirilmedi"
        raise DiffCoverageError(f"git komutu düştü (`git {' '.join(args)}`): {reason}")
    return completed.stdout


def changed_lines(root: Path, base: str, head: str) -> dict[str, set[int]]:
    """`base...head` üçlü nokta aralığındaki değişen satırları döndürür.

    Üçlü nokta bilinçli: `base..head` iki dalın ayrıldığı noktadan sonra
    *base*'e giren değişiklikleri de fark sayar ve yazmadığın satırlardan
    sorumlu tutulursun. `base...head` yalnız head'in ortak atadan bu yana
    getirdiklerini gösterir — `diff-cover`'ın da yaptığı budur.
    """
    raw = _git(root, "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{base}...{head}")
    return parse_unified_diff(raw)


# --------------------------------------------------------------------------
# 4. Kesişim ve rapor
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FileOutcome:
    """Tek bir dosyanın ölçülebilir değişen satırlarının sonucu."""

    path: str
    measurable: tuple[int, ...]
    covered: tuple[int, ...]
    missing: tuple[int, ...]


@dataclass
class Report:
    files: list[FileOutcome] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def total_changed(self) -> int:
        return sum(len(outcome.measurable) for outcome in self.files)

    @property
    def total_covered(self) -> int:
        return sum(len(outcome.covered) for outcome in self.files)

    @property
    def percent(self) -> float | None:
        """Ölçülebilir değişen satır yoksa None — 0/0 asla %100 değildir."""
        if self.total_changed == 0:
            return None
        return 100.0 * self.total_covered / self.total_changed


def _is_test_path(relative: str) -> bool:
    parts = relative.split("/")
    if any(part in TEST_DIRECTORY_NAMES for part in parts[:-1]):
        return True
    basename = parts[-1]
    return any(fnmatch.fnmatchcase(basename, pattern) for pattern in TEST_BASENAME_PATTERNS)


def load_coverage(paths: list[Path]) -> dict[str, set[int]]:
    """Bir ya da daha çok kapsam JSON'unu birleştirir; boş/bozuk olanı reddeder.

    Boş `files` haritası özellikle hata sayılır: toplayıcı hiç satır görmediyse
    araç çalışmamıştır ve devam etmek "değişen her satır kapsanmamış" gibi
    görünen, tamamen anlamsız bir %0 üretir. Yalancı-kırmızı da yalancı-yeşil
    kadar zararlıdır.
    """
    merged: dict[str, set[int]] = {}
    if not paths:
        raise DiffCoverageError("en az bir --coverage dosyası gerekir")
    for path in paths:
        if not path.is_file():
            raise DiffCoverageError(f"kapsam dosyası yok: {path}")
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DiffCoverageError(
                f"kapsam dosyası geçerli JSON değil: {path} — {error}"
            ) from error
        if not isinstance(parsed, dict) or not isinstance(parsed.get("files"), dict):
            raise DiffCoverageError(
                f"kapsam dosyasında `files` sözlüğü yok: {path} — bu dosya "
                f"`{PLUGIN_NAME}` toplayıcısı tarafından üretilmemiş olabilir"
            )
        files = parsed["files"]
        if not files:
            raise DiffCoverageError(
                f"kapsam dosyası boş: {path} — toplayıcı hiç satır görmedi. "
                "pytest eklentisi `-p` ile yüklenmemiş ya da hiç test koşmamış olabilir."
            )
        for name, lines in files.items():
            if not isinstance(lines, list):
                raise DiffCoverageError(f"kapsam dosyasında `{name}` satır listesi değil: {path}")
            merged.setdefault(str(name), set()).update(int(line) for line in lines)
    return merged


def build_report(
    root: Path,
    changed: dict[str, set[int]],
    coverage: dict[str, set[int]],
    *,
    include_tests: bool = False,
    excludes: tuple[str, ...] = (),
) -> Report:
    """Değişen satırlarla kapsamı keser; ölçülemeyeni paydadan düşer."""
    report = Report()
    for relative in sorted(changed):
        lines = changed[relative]
        if not relative.endswith(".py"):
            report.skipped.append(f"{relative}: Python dosyası değil, ölçülmedi")
            continue
        if any(fnmatch.fnmatchcase(relative, pattern) for pattern in excludes):
            report.skipped.append(f"{relative}: --exclude ile dışarıda")
            continue
        if not include_tests and _is_test_path(relative):
            report.skipped.append(f"{relative}: test dosyası (--include-tests ile sayılır)")
            continue
        source = root / relative
        if not source.is_file():
            report.skipped.append(f"{relative}: çalışma ağacında yok (silinmiş ya da taşınmış)")
            continue
        try:
            available = executable_lines(source)
        except (SyntaxError, ValueError, OSError) as error:
            report.skipped.append(f"{relative}: derlenemedi, ölçülemez — {error}")
            continue
        measurable = sorted(lines & available)
        if not measurable:
            report.skipped.append(f"{relative}: değişen satırların hiçbiri çalıştırılabilir değil")
            continue
        executed = coverage.get(relative, set())
        covered = [line for line in measurable if line in executed]
        missing = [line for line in measurable if line not in executed]
        report.files.append(
            FileOutcome(
                path=relative,
                measurable=tuple(measurable),
                covered=tuple(covered),
                missing=tuple(missing),
            )
        )
    return report


def _format_missing(missing: tuple[int, ...], limit: int = 12) -> str:
    shown = ", ".join(str(line) for line in missing[:limit])
    if len(missing) > limit:
        shown += f", … (+{len(missing) - limit})"
    return shown


def print_report(report: Report, threshold: float | None) -> int:
    """Raporu Türkçe basar ve çıkış kodunu döndürür."""
    percent = report.percent
    if percent is None:
        print(f"{MARKER}=PASS (kapsanacak satır yok — değişen çalıştırılabilir satır bulunmadı)")
        for note in report.skipped:
            print(f"  - atlandı: {note}")
        return EXIT_CLEAN

    failed = threshold is not None and percent < threshold
    status = "FAIL" if failed else "PASS"
    if threshold is None:
        suffix = "eşik verilmedi, yalnız rapor"
    else:
        suffix = f"eşik %{threshold:g}"
    print(
        f"{MARKER}={status} (değişen {report.total_changed} satırın "
        f"{report.total_covered} tanesi kapsandı, %{percent:.1f}; {suffix})"
    )
    for outcome in report.files:
        count = len(outcome.measurable)
        ratio = 100.0 * len(outcome.covered) / count
        line = f"  - {outcome.path}: {len(outcome.covered)}/{count} (%{ratio:.1f})"
        if outcome.missing:
            line += f" kapsanmayan: {_format_missing(outcome.missing)}"
        print(line)
    for note in report.skipped:
        print(f"  - atlandı: {note}")
    if threshold is None:
        print("  - eşik için `--fail-under` verilmedi; kapı kırmızı yanamaz (A8' onay bekliyor).")
    return EXIT_BELOW_THRESHOLD if failed else EXIT_CLEAN


# --------------------------------------------------------------------------
# 5. Komut satırı
# --------------------------------------------------------------------------


def run_collect(arguments: argparse.Namespace) -> int:
    """pytest'i kendi eklentimizle koşturur ve kapsam JSON'unu üretir."""
    root = arguments.root.resolve()
    output = arguments.output.resolve()
    working = arguments.tests_root
    working = (root / working).resolve() if not working.is_absolute() else working.resolve()
    if not working.is_dir():
        print(f"{MARKER}=FAIL (test kökü yok: {working})", file=sys.stderr)
        return EXIT_UNUSABLE

    pytest_arguments = list(arguments.pytest_args)
    if pytest_arguments and pytest_arguments[0] == "--":
        pytest_arguments = pytest_arguments[1:]

    environment = os.environ.copy()
    environment[OUTPUT_ENV] = str(output)
    environment[ROOT_ENV] = str(root)
    # Eklenti `scripts.diff_coverage_check` adıyla yükleniyor; pytest başka bir
    # dizinden koşuyorsa depo kökü içe aktarma yolunda olmak zorunda.
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(root) + (os.pathsep + existing if existing else "")

    command = [arguments.python, "-m", "pytest", "-p", PLUGIN_NAME, *pytest_arguments]
    # shell=False; yorumlayıcı yolu çağıran tarafından verilir, kabuk yorumu yoktur.
    completed = subprocess.run(
        command,
        cwd=str(working),
        env=environment,
        check=False,
    )
    if not output.is_file():
        print(
            f"{MARKER}=FAIL (kapsam dosyası yazılmadı: {output}; "
            f"pytest çıkış kodu {completed.returncode})",
            file=sys.stderr,
        )
        return EXIT_UNUSABLE
    try:
        collected = load_coverage([output])
    except DiffCoverageError as error:
        print(f"{MARKER}=FAIL ({error})", file=sys.stderr)
        return EXIT_UNUSABLE
    total = sum(len(lines) for lines in collected.values())
    print(f"DIFF_COVERAGE_COLLECT=OK ({len(collected)} dosya, {total} satır → {output})")
    return completed.returncode


def run_report(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    try:
        coverage = load_coverage([path.resolve() for path in arguments.coverage])
        changed = changed_lines(root, arguments.base, arguments.head)
    except DiffCoverageError as error:
        print(f"{MARKER}=FAIL ({error})", file=sys.stderr)
        return EXIT_UNUSABLE
    report = build_report(
        root,
        changed,
        coverage,
        include_tests=arguments.include_tests,
        excludes=tuple(arguments.exclude),
    )
    return print_report(report, arguments.fail_under)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diff_coverage_check.py",
        description="Bağımlılıksız değişen-satır kapsam kapısı (sys.monitoring + git diff).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Depo kökü (varsayılan: bu betiğin üst dizini).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="pytest'i eklentiyle koşturup kapsam topla.")
    collect.add_argument("--output", type=Path, required=True, help="Yazılacak kapsam JSON'u.")
    collect.add_argument(
        "--tests-root",
        type=Path,
        default=Path("apps/api"),
        help="pytest'in koşacağı dizin (varsayılan: apps/api).",
    )
    collect.add_argument(
        "--python",
        default=sys.executable,
        help="pytest'i koşturacak yorumlayıcı (varsayılan: bu yorumlayıcı).",
    )
    collect.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="`--` sonrası her şey pytest'e aktarılır.",
    )
    collect.set_defaults(handler=run_collect)

    report = subparsers.add_parser("report", help="Değişen satırlarla kapsamı kes.")
    report.add_argument(
        "--coverage",
        type=Path,
        action="append",
        default=[],
        required=True,
        help="Kapsam JSON'u; birden çok kez verilebilir (paralel koşular birleşir).",
    )
    report.add_argument("--base", required=True, help="Karşılaştırma tabanı (örn. origin/main).")
    report.add_argument("--head", default="HEAD", help="Ölçülen uç (varsayılan: HEAD).")
    report.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Yüzde eşiği. VARSAYILANI YOKTUR: verilmezse rapor basılır ve çıkış 0'dır.",
    )
    report.add_argument(
        "--include-tests",
        action="store_true",
        help="Test dosyalarını da paydaya kat (varsayılan: hariç).",
    )
    report.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Depo göreli yola uygulanan ek dışlama kalıbı; birden çok kez verilebilir.",
    )
    report.set_defaults(handler=run_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
