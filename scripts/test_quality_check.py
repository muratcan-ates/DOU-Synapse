#!/usr/bin/env python3
"""Testin bir şey ölçtüğünü sınayan kapı — sözdizimi düzeyinde.

Neden bir kapı gerekiyor: bu depoda test SAYISI bir kanıt olarak kullanılıyor
(`docs_check.mjs` belgelerdeki sayaçları test sayısına bağlıyor, dossier'ların
`metrics` bloğu "passed" sayılarını taşıyor). Sayı arttığı sürece kimse tek tek
bakmıyor. Oysa yeşil yanan bir test, hiçbir şey ölçmediği için de yeşil yanıyor
olabilir; o durumda sayaç yükselir, güven yükselir, kanıt yükselmez.

`ruff` ve `mypy` bunu göremez: her üç kusur da geçerli, tipli, temiz Python'dur.
Kusur davranışta değil, iddianın İÇERİĞİNDE.

Yakalanan üç kusur — hepsi bu depoda gerçekten gözlendi:

1. **sadece-durum-kodu** — testin bütün iddiaları `response.status_code == 2xx`
   biçiminde. Bu "uç başarıyla döndü" der; "doğru şeyi döndürdü" demez. Gövde
   boşalsa, alanlar yer değiştirse, kaynak listesi silinse test yine yeşil yanar.

   Kural **yalnız başarı kodlarında** çalışır. `== 403` ya da `== 404` iddiası tek
   başına da bir şey ölçer: yetkisiz çağrının reddedildiğini. Reddin gövdesi zaten
   boştur; oradan başka bir şey istemek testi güçlendirmez, gürültü üretir.
   `apps/api/tests` altında `status_code == 200` deseninden 220 kullanım var.

2. **raises-totolojisi** — `with pytest.raises(X):` bloğunun içinde `raise`
   deyimlerinin dışında hiçbir ÇAĞRI yok. O zaman istisnayı ne üretecek belirsizdir
   (blok boş ya da yalnız sabit) ya da testin kendisi üretiyordur; iki durumda da
   "kod bu girdide hata veriyor" iddiası ölçülmemiştir.

   `raise` içeren blok tek başına kusur DEĞİLDİR: `pytest.raises(RuntimeError)`
   içinde kasten `raise` edip transaction'ın geri alındığını sınayan test gerçek bir
   mekanizmayı ölçer (`test_admin_readiness.py:137`). Orada raise'in yanında gerçek
   çağrılar vardır ve kural sessiz kalır.

3. **cagrisiz-test** — test gövdesinde hiçbir çağrı yok VE uygulama isimlerinden
   hiçbirine dokunulmuyor. Yalnız kendi kurduğu değişmezleri birbirine eşitliyor.
   `assert HINT_MULTIPLIERS == {...}` bu sınıfa GİRMEZ: orada üretim sabiti okunuyor,
   yani sabit değişirse test kırmızı yanar. Yerel yardımcıyı (`_provider_with_fake`)
   çağıran test de girmez: yardımcı üretim koduna o testin adına dokunur.

**Bilinçli olarak dar.** Kapı "bu test zayıf" demiyor; "bu testin iddiası, koda
dokunmadan da doğru kalır" diyor. Yorumlanabilir bulgu üretmek yerine hiç bulgu
üretmemek tercih edildi: kapının değeri, kırmızı yandığında tartışmasız olması.

**Muafiyet.** Bir bulgu bilinçliyse testin içine gerekçesiyle yazılır:

    # test-quality: sadece-durum-kodu — bu uç gövdesizdir (204), tek kanıt koddur

Susturma değil, YAZILI gerekçe: gerekçesiz muafiyet kabul edilmez ve kapı,
gerekçesi boş bir muafiyeti kusur sayar. Muafiyet, kuralın adını içeren satırın
hemen üstünde ya da test gövdesinin herhangi bir yerinde olabilir.

Kullanım:

    python3 scripts/test_quality_check.py
    python3 scripts/test_quality_check.py apps/api/tests
    python3 scripts/test_quality_check.py --format json

Çıkış kodu 0 temiz, 1 bulgu var. Ağ, veritabanı ve bağımlılık gerektirmez;
dosyaları yalnız okur ve `ast` ile ayrıştırır — test toplamaz, içe aktarmaz.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Varsayılan tarama kökleri. Depoda test tutan her dizin; başka dizin verilirse
#: komut satırı kazanır.
DEFAULT_TARGETS = ("apps/api/tests",)

#: Test dosyası adı deseni — pytest'in kendi toplama kuralıyla aynı.
TEST_FILE = re.compile(r"^test_.*\.py$|^.*_test\.py$")

#: Test fonksiyonu adı deseni.
TEST_FUNCTION = re.compile(r"^test_")

#: Muafiyet yorumu: kuralın adı ve ardından boş olmayan bir gerekçe.
WAIVER = re.compile(r"#\s*test-quality:\s*(?P<rule>[a-z-]+)\s*[—-]\s*(?P<reason>\S.*)$")

#: Uygulama paketlerinin kökleri. Bir testin "üretim koduna dokunduğu" bu
#: köklerden içe aktarılmış bir isim kullanmasıyla anlaşılır.
APPLICATION_ROOTS = frozenset({"app", "evaluation", "scripts", "tests"})

RULE_STATUS_ONLY = "sadece-durum-kodu"
RULE_RAISES_TAUTOLOGY = "raises-totolojisi"
RULE_CALL_FREE = "cagrisiz-test"

RULES = (RULE_STATUS_ONLY, RULE_RAISES_TAUTOLOGY, RULE_CALL_FREE)


@dataclass(frozen=True)
class Finding:
    """Tek bir kusur. `line` testin `def` satırıdır; bulgu oraya yazılır."""

    path: str
    line: int
    test: str
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}  {self.rule}  {self.test} — {self.detail}"


def _imported_application_names(tree: ast.Module) -> set[str]:
    """Dosyanın uygulama paketlerinden içe aktardığı isimler.

    `from app.modules.mastery.service import compute_new_score` → {"compute_new_score"}
    `import app.core.config as config` → {"config"}
    `from app import core` → {"core"}

    Bu küme, "test üretim koduna dokunuyor mu" sorusunun tek ölçütüdür. İsim
    listesine bakmak, çağrı olup olmadığına bakmaktan daha doğru: üretim SABİTİNİ
    okuyan bir test de (çağrı yok) o sabit değişince kırmızı yanar.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level > 0 or root in APPLICATION_ROOTS:
                names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in APPLICATION_ROOTS:
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


def _waivers(source_lines: list[str], node: ast.AST) -> set[str]:
    """Gövdesinde (ve `def` satırında) geçen muafiyetlerin kural adları.

    Gerekçesi boş olan muafiyet SAYILMAZ: `WAIVER` deseni en az bir boşluk-dışı
    karakter ister. Böylece `# test-quality: cagrisiz-test —` yazarak kapı
    susturulamaz; susturmak için neden yazmak gerekir.
    """
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start) or start
    found: set[str] = set()
    for line in source_lines[start - 1 : end]:
        match = WAIVER.search(line)
        if match and match.group("rule") in RULES:
            found.add(match.group("rule"))
    return found


def _is_success_status_compare(node: ast.expr) -> bool:
    """`<bir şey>.status_code == <2xx sabiti>` mi?

    Yalnız BAŞARI kodu sayılır. `== 403` bir yetki iddiasıdır ve tek başına da
    ölçer; reddin gövdesi zaten boştur. `== 200` ise "çalıştı" demekten öteye
    gitmez — kuralın konusu odur.
    """
    if not isinstance(node, ast.Compare):
        return False
    attribute_sides = [node.left, *node.comparators]
    if not any(
        isinstance(side, ast.Attribute) and side.attr == "status_code" for side in attribute_sides
    ):
        return False
    codes = [
        side.value
        for side in attribute_sides
        if isinstance(side, ast.Constant) and isinstance(side.value, int)
    ]
    return bool(codes) and all(200 <= code < 300 for code in codes)


def _assert_tests(node: ast.expr) -> bool:
    """İddia, başarı kodundan BAŞKA bir şeye de bakıyor mu?

    `assert response.status_code == 200 and response.json()["items"]` gibi bileşik
    iddialar gövdeyi de sınar; bunlar kusur değildir.
    """
    if isinstance(node, ast.BoolOp):
        return any(not _is_success_status_compare(value) for value in node.values)
    return not _is_success_status_compare(node)


def _calls_outside_raise(node: ast.AST) -> bool:
    """`raise` deyimlerinin DIŞINDA çalışan bir çağrı var mı?

    İstisna kurucusu (`raise RuntimeError("x")` içindeki `RuntimeError(...)`) bir
    çağrıdır ama hiçbir üretim yolunu yürütmez; sayılmaması gerekir. Bu yüzden
    `ast.Raise` düğümlerinin altı taranmadan geçilir.

    Çağrının hedefine bakılmaz. Testler üretim koduna yerel değişkenler
    (`conn.execute(...)`), fixture'lar (`client.get(...)`) ve yerel yardımcılar
    (`_provider_with_fake(...)`) üzerinden dokunuyor; hedef ismini isim listesiyle
    eşleştirmek bu üç yolu da kaçırır ve kapıyı gürültüye çevirir. Kuralın
    tartışmasız kalması için ölçüt en dar hâliyle tutuldu: HİÇ çağrı yoksa blok
    hiçbir şey yürütmüyordur.

    `await` de yürütme sayılır ve bu bir incelik değil, ölçülmüş bir kusurdu:
    `test_upload_safety.py:234` ve `test_worker_recovery.py:219` coroutine'i önce
    bir değişkene koyup blokta yalnız `await request` yazıyor. Orada `ast.Call`
    düğümü yoktur ama üretim yolu tam olarak o satırda yürür.
    """
    stack: list[ast.AST] = [node]
    while stack:
        current = stack.pop()
        for child in ast.iter_child_nodes(current):
            if isinstance(child, ast.Raise):
                continue
            if isinstance(child, (ast.Call, ast.Await)):
                return True
            stack.append(child)
    return False


def _raise_block_runs_production(block: ast.With | ast.AsyncWith) -> bool:
    """Blok (gövdesi VE kendi `with` öğeleri) üretim kodu yürütüyor mu?

    `with pytest.raises(RuntimeError), gate.hold(...):` biçiminde sınanan şey
    ikinci context manager'ın kendisidir (`test_rate_limit.py:79`: `hold`'un
    `finally` dalı). O çağrı gövdede değil, `with` öğelerindedir; yalnız gövdeye
    bakan bir kural bu testi haksız yere kusurlu sayar.
    """
    for item in block.items:
        call = item.context_expr
        if isinstance(call, ast.Call) and _dotted(call.func).endswith("pytest.raises"):
            continue
        if _calls_outside_raise(ast.Expression(body=item.context_expr)):
            return True
        if isinstance(call, (ast.Call, ast.Await)):
            return True
    return _calls_outside_raise(ast.Module(body=list(block.body), type_ignores=[]))


def _call_root(func: ast.expr) -> str | None:
    """`a.b.c(...)` → "a"; `f(...)` → "f"; başka biçim → None."""
    while isinstance(func, ast.Attribute):
        func = func.value
    return func.id if isinstance(func, ast.Name) else None


def _touches_application(node: ast.AST, application_names: set[str], parameters: set[str]) -> bool:
    """Test uygulama koduna, bir fixture'a ya da herhangi bir çağrıya dokunuyor mu?

    Üç yol da dokunuş sayılır:

    * **Fixture parametresi** — `client`, `session`, `settings` conftest üzerinden
      gerçek nesneleri getirir.
    * **Herhangi bir çağrı** — yerel yardımcı (`_provider_with_fake`) üretim
      koduna testin adına dokunur; çağrının hedefine bakmak bunu kaçırır.
    * **İçe aktarılmış uygulama ismi** — çağrısız okunan üretim sabiti
      (`HINT_MULTIPLIERS`) da testi koda bağlar.

    Geriye yalnız hiçbirine dokunmayan test kalır: kendi kurduğu değişmezleri
    birbirine eşitleyen, kod silinse bile yeşil yanacak test.
    """
    if parameters:
        return True
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            return True
        if isinstance(child, ast.Name) and child.id in application_names:
            return True
        if isinstance(child, ast.Attribute):
            root = _call_root(child)
            if root is not None and root in application_names:
                return True
    return False


def _raises_blocks(node: ast.AST) -> list[ast.With]:
    """Gövdedeki `with pytest.raises(...)` blokları."""
    blocks: list[ast.With] = []
    for child in ast.walk(node):
        if not isinstance(child, (ast.With, ast.AsyncWith)):
            continue
        for item in child.items:
            call = item.context_expr
            if isinstance(call, ast.Call) and _dotted(call.func).endswith("pytest.raises"):
                blocks.append(child)  # type: ignore[arg-type]
                break
    return blocks


def _dotted(func: ast.expr) -> str:
    """`pytest.raises` → "pytest.raises"; çözülemeyen biçim → ""."""
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return ""


def _assertions(node: ast.AST) -> list[ast.Assert]:
    return [child for child in ast.walk(node) if isinstance(child, ast.Assert)]


def _parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """`self` dışındaki parametre adları — pytest'te bunlar fixture'dır."""
    arguments = function.args
    names = {argument.arg for argument in (*arguments.posonlyargs, *arguments.args)}
    names.update(argument.arg for argument in arguments.kwonlyargs)
    return names - {"self", "cls"}


def _check_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    path: str,
    source_lines: list[str],
    application_names: set[str],
) -> list[Finding]:
    waived = _waivers(source_lines, function)
    parameters = _parameters(function)
    findings: list[Finding] = []

    assertions = _assertions(function)
    raises = _raises_blocks(function)

    # 1. Sadece durum kodu. `pytest.raises` kullanan bir testte iddia gövdede
    #    olmayabilir; o yüzden hiç `assert` yoksa bu kural çalışmaz.
    if (
        assertions
        and RULE_STATUS_ONLY not in waived
        and not any(_assert_tests(assertion.test) for assertion in assertions)
    ):
        findings.append(
            Finding(
                path=path,
                line=function.lineno,
                test=function.name,
                rule=RULE_STATUS_ONLY,
                detail=(
                    f"{len(assertions)} iddianın hepsi 2xx `status_code` karşılaştırması; "
                    "gövde, yan etki ya da veritabanı durumu sınanmıyor"
                ),
            )
        )

    # 2. `pytest.raises` totolojisi.
    if RULE_RAISES_TAUTOLOGY not in waived:
        for block in raises:
            if not _raise_block_runs_production(block):
                findings.append(
                    Finding(
                        path=path,
                        line=block.lineno,
                        test=function.name,
                        rule=RULE_RAISES_TAUTOLOGY,
                        detail=(
                            "blokta `raise` dışında hiçbir çağrı yok; "
                            "istisnayı üretecek üretim yolu yürütülmüyor"
                        ),
                    )
                )

    # 3. Çağrısız test. İddiası olmayan test (yalnız kurulum yapan yardımcı) bu
    #    kuralın konusu değildir; kural, iddia eden ama koda dokunmayan testi arar.
    if (
        assertions
        and RULE_CALL_FREE not in waived
        and not _touches_application(function, application_names, parameters)
    ):
        findings.append(
            Finding(
                path=path,
                line=function.lineno,
                test=function.name,
                rule=RULE_CALL_FREE,
                detail=(
                    "gövdede çağrı, fixture ve uygulama ismi yok; "
                    "iddia yalnız testin kendi kurduğu değişmezler üzerinde"
                ),
            )
        )

    return findings


def check_source(source: str, path: str) -> list[Finding]:
    """Tek dosyayı ayrıştırıp bulgularını döndürür.

    Ayrıştırılamayan dosya bulgu değil HATA'dır: sessizce atlanırsa kapı, bozuk
    bir test dosyasının üzerinden yeşil geçer.
    """
    tree = ast.parse(source, filename=path)
    source_lines = source.splitlines()
    application_names = _imported_application_names(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and TEST_FUNCTION.match(
            node.name
        ):
            findings.extend(
                _check_function(
                    node,
                    path=path,
                    source_lines=source_lines,
                    application_names=application_names,
                )
            )
    return sorted(findings, key=lambda finding: (finding.path, finding.line, finding.rule))


def collect_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_file():
            files.append(target)
            continue
        files.extend(
            path
            for path in sorted(target.rglob("*.py"))
            if TEST_FILE.match(path.name) and "__pycache__" not in path.parts
        )
    return files


def check_paths(targets: list[Path]) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files = collect_files(targets)
    for file in files:
        relative = file.relative_to(REPO_ROOT) if file.is_relative_to(REPO_ROOT) else file
        findings.extend(check_source(file.read_text(encoding="utf-8"), str(relative)))
    return findings, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        help=f"Taranacak dosya ya da dizin (varsayılan: {', '.join(DEFAULT_TARGETS)}).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Çıktı biçimi. `json` kanıt dosyasına yazmak içindir.",
    )
    arguments = parser.parse_args(argv)

    targets = [Path(target) for target in arguments.targets] or [
        REPO_ROOT / target for target in DEFAULT_TARGETS
    ]
    missing = [target for target in targets if not target.exists()]
    if missing:
        for target in missing:
            print(f"TEST_QUALITY=FAIL  yol yok: {target}", file=sys.stderr)
        return 1

    findings, scanned = check_paths(targets)

    if arguments.format == "json":
        print(
            json.dumps(
                {
                    "scanned_files": scanned,
                    "findings": [finding.__dict__ for finding in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    if findings:
        print("TEST_QUALITY=FAIL")
        for finding in findings:
            print(f"  - {finding.render()}")
        print(
            f"\n{len(findings)} bulgu / {scanned} dosya. Bilinçliyse teste gerekçeli muafiyet "
            "yorumu ekleyin: `# test-quality: <kural> — <gerekçe>`"
        )
        return 1

    print(f"TEST_QUALITY=PASS ({scanned} dosya tarandı, bulgu yok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
