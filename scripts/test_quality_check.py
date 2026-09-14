#!/usr/bin/env python3
"""Etkin görünüp bir şey kanıtlamayan testleri AST üzerinden yakalar.

Neden bir kapıya ihtiyaç var: yeşil bir test paketi, testlerin bir şey
kanıtladığı anlamına gelmez. Depoda üç sessiz kalıp tekrarlanabiliyor ve
hiçbir lint kuralı bunları görmüyor:

1. **Yalnız durum kodu** — gövdesindeki TEK iddia
   ``assert response.status_code == 200``. Uç noktanın döndürdüğü gövde,
   atıflar, izolasyon: hiçbiri sınanmaz. Uç nokta boş JSON dönmeye başlasa
   test yeşil kalır.
2. **``pytest.raises`` totolojisi** — ``with pytest.raises(X): raise X(...)``.
   Blok, sınanan kodu hiç çağırmaz; yalnızca Python'ın ``raise``
   deyiminin çalıştığını kanıtlar.
3. **Çağrısız test** — adı ``test`` ile başlar ama gövdesinde hiçbir
   fonksiyon/metot çağrısı yoktur. Rapor satırında "geçti" yazar, sınanan
   koda ise hiç dokunulmamıştır.

Bu kapı saf ``ast`` ile çalışır: yeni bağımlılık yok, kod çalıştırılmaz,
ağ ve veritabanı gerekmez.

Kapsam kararı: pytest yalnızca adı ``test`` ile başlayan fonksiyonları
toplar. Ortasında ``test_`` geçen yardımcılar (``make_test_payload`` gibi)
hiçbir zaman koşmaz, dolayısıyla "sınar gibi görünen test" olamazlar ve
1. ile 3. kurallar onları denetlemez. 2. kural ise fonksiyon adından
bağımsızdır; ``pytest.raises`` totolojisi nerede yazılırsa yazılsın
yakalanır.

Kullanım::

    python3 scripts/test_quality_check.py                  # varsayılan yollar
    python3 scripts/test_quality_check.py apps/api/tests    # belirli yol
    python3 scripts/test_quality_check.py --fail-on-warn    # uyarı varsa rc=1

``--fail-on-warn`` verilmediğinde çıkış kodu her zaman 0'dır; bulgular yine
de yazdırılır. Ayrıştırılamayan dosya da bir bulgudur (fail-closed):
"okuyamadım" sessizce "temiz" sayılmaz.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATHS: tuple[str, ...] = ("apps/api/tests", "scripts")
SKIPPED_DIRECTORIES = frozenset({"__pycache__", ".venv", "node_modules", ".git"})

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class Finding:
    """Tek bir kalite uyarısı; ``code`` makine, ``message`` insan içindir."""

    code: str
    path: Path
    line: int
    function: str
    message: str

    def render(self, root: Path) -> str:
        try:
            shown = self.path.resolve().relative_to(root).as_posix()
        except ValueError:
            shown = self.path.as_posix()
        return f"{self.code} {shown}:{self.line} {self.function} — {self.message}"


def _is_test_function(node: FunctionNode) -> bool:
    """pytest'in topladığı adlandırma: ``test`` ile başlayan fonksiyonlar."""
    return node.name.startswith("test")


def _call_name(call: ast.Call) -> str:
    """Çağrılan adın son parçası; ``self.assertEqual`` için ``assertEqual``."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_assertion_call(call: ast.Call) -> bool:
    """``assertEqual`` / ``assert_called_once`` gibi iddia yardımcıları."""
    return _call_name(call).startswith("assert")


def _statement_nodes(body: Sequence[ast.stmt]) -> Iterator[ast.AST]:
    """Gövdedeki tüm düğümler; dekoratörler ve imza varsayılanları hariç."""
    for statement in body:
        yield from ast.walk(statement)


def _touches_status_code(expression: ast.expr) -> bool:
    """``x.status_code == 200`` biçiminde bir karşılaştırma mı?

    Tersi de (``200 == response.status_code``) sayılır: kusur karşılaştırmanın
    yönü değil, gövdeye hiç bakılmamasıdır. Beklenen kodun 200 olması da
    şart değil; 404 bekleyen tek iddialı bir test de aynı boşluğu bırakır.
    """
    if not isinstance(expression, ast.Compare):
        return False
    operands = [expression.left, *expression.comparators]
    return any(
        isinstance(operand, ast.Attribute) and operand.attr == "status_code" for operand in operands
    )


def _is_pytest_raises(expression: ast.expr) -> bool:
    """``pytest.raises(...)`` ya da doğrudan içe aktarılmış ``raises(...)``."""
    if not isinstance(expression, ast.Call):
        return False
    func = expression.func
    if isinstance(func, ast.Attribute):
        return func.attr == "raises" and (
            isinstance(func.value, ast.Name) and func.value.id == "pytest"
        )
    if isinstance(func, ast.Name):
        return func.id == "raises"
    return False


def _raised_expression_calls(raise_node: ast.Raise) -> set[int]:
    """``raise X(f())`` içindeki çağrıların kimlikleri.

    Bunlar "sınanan kodu çağırdık" sayılmaz: istisnayı elle kuran ifadenin
    parçalarıdır. ``from`` nedeni de aynı kapsamdadır.
    """
    identities: set[int] = set()
    for part in (raise_node.exc, raise_node.cause):
        if part is None:
            continue
        for node in ast.walk(part):
            if isinstance(node, ast.Call):
                identities.add(id(node))
    return identities


def _companion_manager_calls(node: ast.With | ast.AsyncWith) -> bool:
    """``with pytest.raises(X), gate.hold(...):`` gibi bir eşlikçi var mı?

    Aynı ``with`` satırındaki ikinci bağlam yöneticisi sınanan kodun ta
    kendisi olabilir; o zaman gövdedeki ``raise`` bilinçli bir tetikleyicidir
    (ör. ``finally`` kolunun kilidi bıraktığını göstermek) ve blok totoloji
    değildir.
    """
    return any(
        isinstance(item.context_expr, ast.Call) and not _is_pytest_raises(item.context_expr)
        for item in node.items
    )


def _is_tautological_raises(body: Sequence[ast.stmt]) -> bool:
    """Blok, istisnayı kendisi fırlatıyor ve başka hiçbir şey çağırmıyor mu?"""
    raises: list[ast.Raise] = []
    calls: list[ast.Call] = []
    for node in _statement_nodes(body):
        if isinstance(node, ast.Raise):
            raises.append(node)
        elif isinstance(node, ast.Call):
            calls.append(node)
    if not raises:
        return False
    excluded: set[int] = set()
    for raise_node in raises:
        excluded |= _raised_expression_calls(raise_node)
    return not any(id(call) not in excluded for call in calls)


class _Inspector(ast.NodeVisitor):
    """Tek bir modülü gezip üç kuralı da uygular."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self._stack: list[str] = []

    @property
    def _scope(self) -> str:
        return ".".join(self._stack) if self._stack else "<modül>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with(node)

    def _visit_function(self, node: FunctionNode) -> None:
        self._stack.append(node.name)
        if _is_test_function(node):
            self._check_status_only_assert(node)
            self._check_missing_call(node)
        self.generic_visit(node)
        self._stack.pop()

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        raises_block = any(_is_pytest_raises(item.context_expr) for item in node.items)
        tautological = (
            raises_block
            and not _companion_manager_calls(node)
            and _is_tautological_raises(node.body)
        )
        if tautological:
            self.findings.append(
                Finding(
                    code="TAUTOLOGICAL_RAISES",
                    path=self.path,
                    line=node.lineno,
                    function=self._scope,
                    message=(
                        "pytest.raises bloğu istisnayı kendisi fırlatıyor; "
                        "sınanan kod hiç çağrılmıyor"
                    ),
                )
            )
        self.generic_visit(node)

    def _check_status_only_assert(self, node: FunctionNode) -> None:
        asserts: list[ast.Assert] = []
        calls: list[ast.Call] = []
        for element in _statement_nodes(node.body):
            if isinstance(element, ast.Assert):
                asserts.append(element)
            elif isinstance(element, ast.Call):
                calls.append(element)
        if len(asserts) != 1 or not _touches_status_code(asserts[0].test):
            return
        if any(_is_assertion_call(call) for call in calls):
            # assertEqual / assert_called_once gibi bir yardımcı da varsa
            # test yalnız durum koduna bakmıyor demektir.
            return
        self.findings.append(
            Finding(
                code="STATUS_ONLY_ASSERT",
                path=self.path,
                line=asserts[0].lineno,
                function=self._scope,
                message=(
                    "tek iddia yalnız status_code'a bakıyor; yanıt gövdesi, "
                    "atıflar ve izolasyon sınanmıyor"
                ),
            )
        )

    def _check_missing_call(self, node: FunctionNode) -> None:
        if any(isinstance(element, ast.Call) for element in _statement_nodes(node.body)):
            return
        self.findings.append(
            Finding(
                code="NO_CALL_TEST",
                path=self.path,
                line=node.lineno,
                function=self._scope,
                message=(
                    "gövdede hiçbir fonksiyon/metot çağrısı yok; test sınanan koda hiç dokunmuyor"
                ),
            )
        )


def inspect_source(source: str, path: Path) -> list[Finding]:
    """Kaynak metni denetle; ayrıştırılamıyorsa bunu da bir bulgu say."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return [
            Finding(
                code="UNPARSEABLE",
                path=path,
                line=error.lineno or 1,
                function="<modül>",
                message=f"dosya ayrıştırılamadı: {error.msg}",
            )
        ]
    inspector = _Inspector(path)
    inspector.visit(tree)
    return inspector.findings


def inspect_file(path: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        return [
            Finding(
                code="UNREADABLE",
                path=path,
                line=1,
                function="<modül>",
                message=f"dosya okunamadı: {error}",
            )
        ]
    return inspect_source(source, path)


def _python_files(target: Path) -> Iterator[Path]:
    if target.is_file():
        if target.suffix == ".py":
            yield target
        return
    for path in sorted(target.rglob("*.py")):
        if SKIPPED_DIRECTORIES.intersection(path.parts):
            continue
        yield path


def inspect_paths(targets: Iterable[Path]) -> list[Finding]:
    """Verilen dosya/dizinleri denetle; bulguları kararlı sırayla döndür."""
    findings: list[Finding] = []
    for target in targets:
        if not target.exists():
            findings.append(
                Finding(
                    code="MISSING_PATH",
                    path=target,
                    line=1,
                    function="<modül>",
                    message="denetlenecek yol bulunamadı",
                )
            )
            continue
        for path in _python_files(target):
            findings.extend(inspect_file(path))
    return sorted(
        findings,
        key=lambda finding: (finding.path.as_posix(), finding.line, finding.code),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Etkin görünüp bir şey kanıtlamayan testleri AST ile yakalar. "
            "Yeni bağımlılık yok; kod çalıştırılmaz."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help=f"denetlenecek dosya/dizinler (varsayılan: {', '.join(DEFAULT_PATHS)})",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="bulgu varsa çıkış kodu 1 olsun (kapıyı zorlayıcı moda alır)",
    )
    arguments = parser.parse_args(argv)

    targets = arguments.paths or [REPO_ROOT / name for name in DEFAULT_PATHS]
    findings = inspect_paths(targets)
    for finding in findings:
        print(finding.render(REPO_ROOT))
    print(f"TEST_QUALITY_WARNINGS={len(findings)}")
    if findings and arguments.fail_on_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
