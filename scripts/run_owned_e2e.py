"""Own the synthetic E2E API lifecycle and account for every remaining audit row.

The caller provisions and pins an exclusive synthetic database first. This tool
does not discover ownership, change database privileges, or delete audit rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

import e2e_audit_guard as guard


class Phase(NamedTuple):
    """Kendi API süreciyle koşan bir faz.

    `slug` tek kaynaktır: hem dosya/dizin adı hem de playwright.config.ts'in
    okuduğu E2E_PHASE değeridir. `budget` None ise fazın tavanı --test-timeout'tur.
    `reserve`, bu fazın DUVAR SAATİ payıdır: tarayıcı beklemesi ARTI fazın kendi
    ek yükü (port sondası, hazır olma beklemesi, iki guard anlık görüntüsü,
    kapanış). Önceki fazlar bu payı yiyemez.
    """

    slug: str
    flags: Mapping[str, str]
    budget: float | None
    reserve: float


#: İki simülasyon bayrağı aynı anda açılamaz, bu yüzden üç ayrı API süreci.
#: Ana faz önce koşar: 87 vakanın 78'ini ve soğuk web derlemesini o taşır.
#: Simülasyon fazlarının derlemesi artımlıdır (aynı ağaç, aynı NEXT_PUBLIC_API_URL),
#: bu yüzden payları soğuk derlemeye göre değil gerçek maliyetlerine göre ölçüldü.
#: DİKKAT — `grounded` ve `ratelimit` satırlarındaki dört sayı (420/260, 300/210)
#: HÂLÂ ÖLÇÜLMEDİ: ilk fazlı CI koşusunda (34926253846) `grounded` kendi API
#: sürecine hiç ulaşamadı (`WEB_PORT_BUSY`, 15.052 sn = port sondasının tam zaman
#: aşımı) ve `ratelimit` hiç başlamadı. Ölçüm için gereken şey bütçe değil, bu
#: dosyadaki port düzeltmesinin bir CI koşusunda yeşil `phases[].seconds`
#: üretmesidir; o koşudan sonra bu dört sayı yeniden ayarlanmalıdır.
#: Kapsam (ölçüldü, `playwright test --list`): `grounded` 6 vaka (üç `kind` ×
#: iki test), `ratelimit` 3 vaka; toplam 9. Varsayılan listeleme 87, ana faz 78,
#: fark tam 9 — yani iki dosyanın tamamı simülasyon fazlarında koşar.
PHASES = (
    Phase("main", {}, None, 0.0),
    Phase("grounded", {"LLM_SIMULATE_GROUNDED_FEEDBACK": "1"}, 420.0, 260.0),
    Phase("ratelimit", {"LLM_SIMULATE_RATE_LIMIT": "1"}, 300.0, 210.0),
)
#: Fazın tarayıcı beklemesi DIŞINDA harcadığı duvar saati için pay. Bu süre
#: hiçbir fazın `budget`'ine girmez; sayılmazsa sessizce sonraki fazın payından
#: düşer ve son faz hiç başlamaz.
#: ÖLÇÜM (koşu 34926253846, `main`): 723.145 sn faz − 720.0 sn tarayıcı = 3.145 sn
#: gerçek ek yük. Ama o fazın guard baseline'ı BOŞTU (`baselineCount: 0`), yani
#: 3.145 alt sınırdır; üstelik pay artık `BROWSER_INTERRUPT_GRACE` (25 sn) iptal
#: zincirini de kapatmak zorunda. 60 bilerek ~2 kat üstte bırakıldı: bu sayı
#: küçültülürse bütçe aşan bir faz, teardown'u biterken sonraki fazın payını yer.
PHASE_OVERHEAD = 60.0
#: Sonraki fazlara ayrılan toplam duvar saati.
RESERVE_TOTAL = sum(phase.reserve for phase in PHASES)
#: Bütün fazların VARSAYILAN toplam duvar saati tavanı. ci.yml işinin kendi
#: sınırı 30 dk ve apt/uv/bun/playwright kurulumunu da kapsıyor; iş SIGKILL
#: yerse result.json HİÇ yazılmaz, yani kapıdan önce durmak zorundayız.
#: Operatör --test-timeout'u yükseltirse son tarih birlikte uzar (aşağıya bak).
#: ÖLÇÜM (E2E işini gerçekten koşan 29 CI koşusu): iş kurulumu (iş başlangıcı →
#: E2E adımı) min 46 · p50 55 · maks 80 sn; adım sonrası kuyruk maks 7 sn;
#: `provision_ci_e2e.py` maks 2.3 sn. Ham boşluk 1800 − 80 − 7 − 3 = 1710 sn.
#: Pay 270 sn ayrıldı; ağırlığı SOĞUK bağımlılık önbelleği: 29 koşunun hepsinde
#: "API ve web bağımlılıkları" adımı 15-32 sn sürdü, yani hepsi sıcak geri
#: yüklemeydi — önbellek düşünce `bunx playwright install` gerçek indirmeye döner.
#: 1250 bu boşluğun 460 sn'sini kullanmadan bırakıyordu; ölçülen tavan 1440'tır.
#: 1440 ile ana faz TAM bütçesini yakarken bile `grounded` tavanının tamamını
#: (420) alır — 34926253846'da 256.9'a sıkışmış ve `ratelimit` hiç koşmamıştı.
OVERALL_BUDGET = 1440.0
#: Bu kadar tarayıcı süresi kalmadıysa faz başlatmak yerine açık kodla durulur.
#: Anlamlı olması için ısınmış bir `next build` artı birkaç vakayı kapsamalı.
PHASE_FLOOR = 150.0
#: --test-timeout için akla yatkın üst sınır; `nan` ve negatif değerleri de eler.
MAX_TEST_TIMEOUT = 7200.0
#: Bütçesini aşan tarayıcıya, SIGINT'ten sonra KENDİ web sunucusunu kapatması
#: için verilen süre. Playwright teardown'u ters sırada koşar ve web sunucusunu
#: EN SON öldürür: önce çalışanlar durur, sonra `global-teardown.ts` psql
#: temizliğini yapar. Bu yüzden pay tek bir sinyal gecikmesi değil, o zincirin
#: tamamıdır. Yalnız bütçe aşımı yolunda harcanır; normal bitişte tarayıcı çoktan
#: çıkmıştır ve `stop_browser_group` hiç sinyal göndermez.
BROWSER_INTERRUPT_GRACE = 25.0


def source_hashes(repo: Path) -> dict[str, str]:
    paths: set[Path] = set()
    for directory, suffixes in {
        "apps/api/app": {".py"},
        "apps/web/app": {".ts", ".tsx", ".css"},
        "apps/web/components": {".ts", ".tsx", ".css"},
        "apps/web/lib": {".ts", ".tsx"},
        "apps/web/e2e": {".ts"},
        "supabase/migrations": {".sql"},
        "scripts": {".py"},
    }.items():
        paths.update(p for p in (repo / directory).rglob("*") if p.suffix in suffixes)
    paths.update(
        repo / p
        for p in (
            "apps/web/playwright.config.ts",
            "apps/web/package.json",
            "docs/kvkk.md",
            "apps/web/next.config.ts",
            "apps/web/tsconfig.json",
            ".github/workflows/ci.yml",
            "supabase/seed_demo.sql",
            "supabase/local_dev_setup.sql",
        )
    )
    return {
        str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def child_environment(
    repo: Path, pins: dict, output: Path, web_port: int, *, slug: str, flags: Mapping[str, str]
) -> dict[str, str]:
    # No ambient provider secrets, PG routing, .env file, or app configuration.
    env = {k: os.environ[k] for k in ("PATH", "LANG", "TZ", "SYSTEMROOT") if k in os.environ}
    address = f"127.0.0.1:{pins['port']}/{pins['databaseName']}"
    env.update(
        {
            "PYTHONPATH": str(repo / "apps/api"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "ENVIRONMENT": "local",
            "DEV_AUTH_ENABLED": "true",
            "DATABASE_URL": f"postgresql+psycopg://dou_app:dou_app_local@{address}",
            "WORKER_DATABASE_URL": f"postgresql+psycopg://dou_worker:dou_worker_local@{address}",
            "CORS_ORIGINS": json.dumps([f"http://localhost:{web_port}"]),
            "QUESTION_AUTHORING_ENABLED": "true",
            "STUDENT_ASSESSMENT_WORKSPACE_ENABLED": "true",
            "EMBEDDING_PROVIDER": "hashing",
            "LLM_FAKE_PROVIDER": "true",
            "EVAL_RUNTIME_ENABLED": "false",
            "GROQ_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "STORAGE_BACKEND": "local",
            # Her fazın kendi depo kökü: sonraki faz önceki fazın yüklediği
            # belgeleri servis edemez, "faz arası durum yok" iddiası doğru kalır.
            "STORAGE_ROOT": str(output / f"storage-{slug}"),
        }
    )
    # Simülasyon bayrağı YALNIZ API sürecine girer. Bayrağı web ortamına da
    # vermek API'yi değiştirmez (provider_fallback.py ve question_gen.py onu
    # kendi süreçlerinde okur) ama ileride bir testin process.env'e bakıp
    # simülasyon yapmayan API'ye karşı yeşil yanmasına kapı açardı.
    env.update(flags)
    return env


def serve_owned(fd: int) -> int:
    """A private parent pipe requests graceful Uvicorn shutdown, then real wait.

    EOF also shuts down if the controller disappears. No test route, timer, or
    application monkeypatch is installed. Signals remain Uvicorn's fallback.
    """
    import uvicorn

    listener = socket.socket(fileno=fd)
    server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="info", lifespan="on"))
    control_received = False
    finished = threading.Event()

    def control() -> None:
        nonlocal control_received
        # A daemon blocked on BufferedReader.readline can abort Python during
        # startup failure. Raw pipe reads and a bounded join release the reader.
        while not finished.is_set():
            try:
                readable, _, _ = select.select([sys.stdin.fileno()], [], [], 0.1)
                if not readable:
                    continue
                control_received = os.read(sys.stdin.fileno(), 16) == b"stop\n"
            except OSError:
                control_received = False
            server.should_exit = True
            return

    reader = threading.Thread(target=control, daemon=True, name="owned-e2e-control")
    reader.start()
    try:
        server.run(sockets=[listener])
    finally:
        finished.set()
        reader.join(timeout=1)
        listener.close()
    lifecycle = server.lifespan
    clean = (
        not reader.is_alive()
        and server.started
        and control_received
        and lifecycle.startup_event.is_set()
        and lifecycle.shutdown_event.is_set()
        and not lifecycle.startup_failed
        and not lifecycle.shutdown_failed
        and not lifecycle.error_occurred
    )
    return 0 if clean else 1


def stop_browser_group(
    process: subprocess.Popen,
    *,
    grace: float = BROWSER_INTERRUPT_GRACE,
    killpg: Callable[[int, int], None] = os.killpg,
) -> str:
    """Bütçeyi aşan tarayıcı sürecini ÖNCE SIGINT ile durdurur.

    Playwright web sunucusunu `detached: true` ile AYRI bir süreç grubu VE
    oturumunda başlatır (playwright-core/lib/coreBundle.js, `launchProcess`),
    bu yüzden bizim `killpg`imiz oraya tanım gereği ulaşmaz. Onu kapatan tek
    yol Playwright'ın KENDİ iptal zinciridir: yalnız SIGINT'in bir işleyicisi
    vardır (runner'daki `FixedNodeSIGINTHandler`) ve teardown web sunucusu
    grubunu kendi pid'iyle `process.kill(-pid)` ederek öldürür. SIGTERM'in
    işleyicisi YOKTUR — süreç anında ölür, 'exit' olayı hiç yayılmaz ve
    `next start` portta öksüz kalır.

    Ölçüldü (bu depoda, Playwright 1.62.1, üç tekrar): süreç grubuna SIGTERM
    gönderildiğinde port 20 sn sonra HÂLÂ tutuluyordu; SIGINT gönderildiğinde
    aynı port anında serbest kaldı. CI'daki iz: koşu 34926253846, `grounded`
    fazı `WEB_PORT_BUSY` (15.052 sn = `wait_web_port_free`'nin tam zaman aşımı).

    İKİNCİ BİR SIGINT GÖNDERİLMEZ: teardown koşucusunun kendi SIGINT gözcüsü
    vardır ve ikinci sinyal tam da web sunucusunu öldüren adımı iptal eder.
    Bu yüzden basamaklar SIGINT → SIGTERM → SIGKILL'dir, SIGINT → SIGINT değil.
    """
    if process.poll() is not None:
        return "exited-before-stop"
    # Yalnız yukarıda `start_new_session=True` ile yaratılan grup bu koşuya ait.
    escalation = (
        (signal.SIGINT, grace, "interrupted"),
        (signal.SIGTERM, 10.0, "forced-terminate"),
        (signal.SIGKILL, 10.0, "forced-kill"),
    )
    last = len(escalation) - 1
    for index, (sig, timeout, observation) in enumerate(escalation):
        try:
            killpg(process.pid, sig)
        except ProcessLookupError:
            # Grup poll() ile killpg arasında ölmüş olabilir. Bu istisna eskiden
            # dışarı kaçıp bütçe aşımını OWNED_E2E_FAILED diye raporlatıyordu;
            # çocuğu yine de reap etmek gerekir, o yüzden yutulur.
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if index == last:
                raise
            continue
        return observation
    raise guard.GuardError("BROWSER_ESCALATION_EXHAUSTED")


def stop_owned_api(process: subprocess.Popen, timeout: float = 30) -> tuple[int, str]:
    if process.poll() is not None:
        return process.wait(), "exited-before-stop"
    stop_kind = "graceful-pipe-and-wait"
    try:
        process.stdin.write(b"stop\n")
        process.stdin.flush()
        process.stdin.close()
    except (BrokenPipeError, OSError):
        stop_kind = "control-pipe-failed"
    try:
        return process.wait(timeout=timeout), stop_kind
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            return process.wait(timeout=10), "forced-terminate"
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait(timeout=10), "forced-kill"


def wait_ready(process: subprocess.Popen, origin: str, timeout: float = 40) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        guard.require(process.poll() is None, "OWNED_API_EXITED_BEFORE_READY")
        try:
            with opener.open(Request(origin + "/health/ready"), timeout=1) as response:  # noqa: S310 — pinned numeric HTTP origin.
                if response.status == 200:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise guard.GuardError("OWNED_API_NOT_READY")


def wait_web_port_free(web_port: int, timeout: float = 15) -> None:
    """Önceki fazın web sunucusu portu bırakmadan sonraki faz başlamaz.

    playwright.config.ts `reuseExistingServer: false` olduğu için port doluysa
    Playwright çocuk süreçte "is already used" fırlatır; bu yaşam döngüsü hatası
    aksi hâlde sıradan bir test hatası gibi okunurdu.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", web_port), timeout=0.2).close()
        except OSError:
            return
        time.sleep(0.1)
    raise guard.GuardError("WEB_PORT_BUSY")


def run_guard(command: list[str], extra: list[str], log: Path) -> int:
    """Guard evresini koşar; çıktı yalnız bir kez yazılabilen loga girer.

    `Path.write_bytes` sessizce kısaltırdı: fazlı düzende kanıt kaybının hata
    üretmeyen tek noktası burasıydı.
    """
    completed = subprocess.run([*command, *extra], capture_output=True, check=False)  # noqa: S603 — fixed colocated guard, validated pins.
    with log.open("xb") as stream:
        stream.write(completed.stdout + completed.stderr)
    return completed.returncode


def read_accounting(audit_directory: Path, receipt: bytes, run_id: str) -> dict[str, object]:
    """Fazın son muhasebesini O FAZIN makbuzuna bağlar.

    scope, target.json ve quiescence alanları fazlar arasında bayt bayt aynıdır
    (runId ve targetId paylaşılır), bu yüzden guard tek başına çapraz bağlanmış
    bir dizini veya bayat bir makbuzu fark edemez. Kalan tek pozitif kanıt,
    final-accounting.json'un içindeki hash'lerin bu fazın dosyalarıyla eşleşmesidir.

    SINIR: `private_read` 4 MiB okur. final-accounting.json baseline'dan büyüktür
    (afterRows artı unexpectedNewRows); guard'ın MAX_ROWS=20000 sınırında bu ~2 MB
    eder, yani yalnız baseline boşken 20 bin satırın tamamının beklenmedik çıktığı
    patolojik durumda tavan aşılır ve sonuç AUDIT_ACCOUNTING_UNREADABLE olur.
    """
    path = audit_directory / "final-accounting.json"
    if not path.exists():
        # finish satır uyuşmazlığında 1, guard hatasında 2 döner; ikincisinde
        # dosya hiç yazılmaz, yani hiçbir satır raporlanmamıştır.
        return {"reconciled": False, "code": "AUDIT_ACCOUNTING_MISSING", "rowDamage": None}
    try:
        accounting = json.loads(guard.private_read(path))
        baseline = guard.private_read(audit_directory / "baseline.json")
        matched = (
            accounting["quiescenceSha256"] == guard.digest(receipt)
            and accounting["baselineSha256"] == guard.digest(baseline)
            and accounting["scope"]["runId"] == run_id
        )
        damage = {
            "missing": len(accounting["missingBaselineIds"]),
            "changed": len(accounting["changedBaselineIds"]),
            "unexpected": len(accounting["unexpectedNewRows"]),
        }
    except (guard.GuardError, OSError, ValueError, KeyError, TypeError):
        return {"reconciled": False, "code": "AUDIT_ACCOUNTING_UNREADABLE", "rowDamage": None}
    if not matched:
        return {"reconciled": False, "code": "AUDIT_ACCOUNTING_CROSSWIRED", "rowDamage": damage}
    return {"reconciled": True, "code": None, "rowDamage": damage}


def row_damage(record: dict[str, object]) -> dict[str, int] | None:
    """Fazın korunmuş satırlarındaki kayıp/değişim/beklenmeyen sayıları."""
    damage = record.get("rowDamage")
    return damage if isinstance(damage, dict) else None


def phase_failure(phase: Phase, code: str, budget: float) -> dict[str, object]:
    """Kendi API sürecine hiç ulaşamamış fazın kaydı; uzlaştırılmamış sayılır."""
    return {
        "phase": phase.slug,
        "status": "FAIL",
        "simulation": sorted(phase.flags) or None,
        "errorCode": code,
        "auditReconciled": False,
        "rowDamage": None,
        "budgetSeconds": round(budget, 3),
    }


def run_phase(
    phase: Phase,
    args: argparse.Namespace,
    repo: Path,
    pins: dict,
    output: Path,
    target_id: str,
    budget: float,
) -> dict[str, object]:
    """Tek fazı kendi API süreci ve kendi denetim muhasebesiyle koşar."""
    phase_started = time.monotonic()
    audit_directory = output / "audit" / phase.slug
    api_cwd = output / f"api-cwd-{phase.slug}"
    guard_command = [
        sys.executable,
        str(Path(__file__).with_name("e2e_audit_guard.py")),
        "--pins",
        str(args.pins),
        "--pins-sha256",
        args.pins_sha256,
        "--passfile",
        str(args.passfile),
        "--directory",
        str(audit_directory),
        "--run-id",
        args.run_id,
        "--execute",
    ]
    playwright_code = 1
    api_code = None
    stop_kind = "not-started"
    browser_stop = "not-started"
    error_code = None
    api = None
    browser = None
    capture_env: dict[str, str] = {}
    # SO_REUSEADDR olmadan ikinci faz önceki fazın TIME_WAIT soketlerine takılır.
    # SO_REUSEPORT değil: o, yabancı bir sürecin aynı portu paylaşmasına açıkça
    # izin verirdi. SO_REUSEADDR Linux'ta (CI) canlı bir LISTEN soketiyle hâlâ
    # çakışır; BSD/macOS'ta yabancı bir 0.0.0.0 dinleyicisiyle örtüşmeye izin
    # verebilir, yani yerel koşuda bu kontrol tek başına sahiplik kanıtı değildir.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # İlk faz dahil HER fazda sondalanır. Playwright web sunucusunu
        # `detached: true` ile kendi süreç grubunda başlatır, bu yüzden bütçe
        # aşımında gönderdiğimiz killpg ona ULAŞMAZ ve `next start` portta
        # öksüz kalabilir. İlk fazın önündeki öksüz de (önceki yerel koşudan)
        # aynı şekilde açık WEB_PORT_BUSY'ye çevrilir, sıradan bir test
        # hatasına değil.
        wait_web_port_free(args.web_port)
        api_cwd.mkdir(mode=0o700, parents=False, exist_ok=False)
        # Dinleyici begin'den ÖNCE bağlanır: ters sırada, bağlanamayan bir faz
        # hiçbir zaman uzlaştırılamayacak bir baseline bırakırdı.
        try:
            listener.bind(("127.0.0.1", urlsplit(pins["apiOrigin"]).port))
            listener.listen(128)
        except OSError as error:
            raise guard.GuardError("OWNED_API_PORT_BUSY") from error
        begin_code = run_guard(
            guard_command, ["--phase", "begin"], output / f"guard-begin-{phase.slug}.log"
        )
        guard.require(begin_code == 0, "AUDIT_BEGIN_FAILED")
        capture_env = json.loads(guard.private_read(audit_directory / "environment.json"))
        guard.require(
            set(capture_env)
            == {
                "E2E_RUN_ID",
                "E2E_DATABASE_NAME",
                "E2E_API_URL",
                "E2E_AUDIT_TARGET_ID",
                "E2E_AUDIT_DIR",
            },
            "AUDIT_ENV_SCHEMA",
        )
        # Guard'ın ürettiği tek faz-ayırt edici dize E2E_AUDIT_DIR'dir; diğer
        # alanlar fazlar arasında bayt bayt aynı olduğundan çapraz bağlanmış bir
        # dizini yalnız burada yakalayabiliriz.
        guard.require(
            capture_env["E2E_RUN_ID"] == args.run_id
            and capture_env["E2E_AUDIT_TARGET_ID"] == target_id
            and capture_env["E2E_AUDIT_DIR"] == str(audit_directory / "capture"),
            "AUDIT_CAPTURE_SCOPE",
        )
        api_env = child_environment(
            repo, pins, output, args.web_port, slug=phase.slug, flags=phase.flags
        )
        # The browser requires the user's runtime/browser paths, but inherits no
        # database route or application secrets. The private passfile is explicit.
        web_env = {
            k: os.environ[k]
            for k in (
                "PATH",
                "HOME",
                "LANG",
                "TZ",
                "CI",
                "PG_BIN",
                "NODE_EXTRA_CA_CERTS",
                "NODE_OPTIONS",
                "PLAYWRIGHT_BROWSERS_PATH",
            )
            if k in os.environ
        }
        web_env.update(capture_env)
        if pins["issuer"] == "github-owned-service":
            web_env["GITHUB_ACTIONS"] = "true"
        web_env.update(
            PGHOST="127.0.0.1",
            PGHOSTADDR="127.0.0.1",
            PGPORT=str(pins["port"]),
            PGUSER=pins["dbaRole"],
            PGPASSFILE=str(args.passfile),
            E2E_PORT=str(args.web_port),
            E2E_WEBPACK_BUILD="1" if args.webpack else "0",
            NEXT_TELEMETRY_DISABLED="1",
            # API tarafı (child_environment) DEV_AUTH_ENABLED=true ile kalkıyor; web
            # L5'ten beri giriş ekranını bu bayrakla kapılıyor. Bayrak taşınmayınca
            # ekran "Oturum açma henüz yapılandırılmadı" diyor ve giriş bekleyen her
            # test zaman aşımına düşüyor (OWNED_E2E_FAILED, 14 Eylül 2026). Yalnız bu
            # izole sentetik hedefte açılır; üretim kapısı değişmez.
            NEXT_PUBLIC_DEV_AUTH="true",
            NEXT_PUBLIC_SUPABASE_URL="",
            NEXT_PUBLIC_SUPABASE_ANON_KEY="",
            GROQ_API_KEY="",
            GEMINI_API_KEY="",
            OPENAI_API_KEY="",
            # playwright.config.ts fazı bu değişkenle seçer; kurulmazsa liste değişmez.
            E2E_PHASE=phase.slug,
        )
        # Dinleyici yukarıda bağlandı ve çocuğa olduğu gibi devredilir. Başka
        # bir servis portu işgal ederek hazır olma kontrolünü geçemez.
        with (
            (output / f"api-{phase.slug}.log").open("xb") as api_log,
            (output / f"playwright-{phase.slug}.log").open("xb") as web_log,
        ):
            api = subprocess.Popen(  # noqa: S603 — current interpreter and verified controller.
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--serve-owned",
                    str(listener.fileno()),
                ],
                env=api_env,
                cwd=api_cwd,
                pass_fds=(listener.fileno(),),
                stdin=subprocess.PIPE,
                stdout=api_log,
                stderr=subprocess.STDOUT,
            )
            listener.close()
            try:
                wait_ready(api, pins["apiOrigin"])
                browser = subprocess.Popen(
                    ["bun", "run", "test:e2e", "--workers=1"],  # noqa: S607 — CI-provisioned Bun on explicit runtime PATH.
                    cwd=repo / "apps/web",
                    env=web_env,
                    stdin=subprocess.DEVNULL,
                    stdout=web_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                playwright_code = browser.wait(timeout=budget)
            finally:
                try:
                    if browser is not None:
                        browser_stop = stop_browser_group(browser)
                finally:
                    api_code, stop_kind = stop_owned_api(api)
    except guard.GuardError as error:
        error_code = str(error)
    except subprocess.TimeoutExpired:
        # Tarayıcı bütçesini aşmakla, durdurulamayan API çocuğu aynı istisnayı
        # kullanır; ayırmazsak bütçe aşımı "reaped edilemeyen çocuk" diye okunur.
        error_code = (
            "OWNED_API_UNREAPABLE" if stop_kind == "not-started" else "PLAYWRIGHT_BUDGET_EXCEEDED"
        )
    except Exception:
        error_code = "OWNED_E2E_FAILED"
    finally:
        listener.close()
    finish_code = None
    accounting: dict[str, object] = {
        "reconciled": False,
        "code": "AUDIT_NOT_RECONCILED",
        "rowDamage": None,
    }
    if api is not None and api_code == 0 and stop_kind == "graceful-pipe-and-wait":
        # Playwright'ın sıfırdan farklı çıkışı da BURADAN raporlanır: guard bunu
        # FAIL'e çevirir. Kirli kapanışta makbuz UYDURULMAZ; guard zaten reddeder.
        quiescence = {
            "version": 1,
            "runId": args.run_id,
            "targetId": capture_env["E2E_AUDIT_TARGET_ID"],
            "ownedApiPid": api.pid,
            "ownedApiExitCode": api_code,
            "playwrightExitCode": playwright_code,
            "state": "stopped",
        }
        # Faz etiketi yalnız DOSYA ADINDA yaşar: guard makbuzun alan kümesini
        # birebir karşılaştırır, fazladan anahtar QUIESCENCE_SCHEMA'yı düşürür.
        path = output / f"quiescence-{phase.slug}.json"
        receipt = guard.private_write(path, quiescence)
        finish_code = run_guard(
            guard_command,
            ["--phase", "finish", "--quiescence-receipt", str(path)],
            output / f"guard-finish-{phase.slug}.log",
        )
        accounting = read_accounting(audit_directory, receipt, args.run_id)
    damage = accounting["rowDamage"]
    passed = (
        error_code is None
        and playwright_code == 0
        and api_code == 0
        and stop_kind == "graceful-pipe-and-wait"
        and finish_code == 0
        and accounting["reconciled"] is True
    )
    return {
        "phase": phase.slug,
        "status": "PASS" if passed else "FAIL",
        "simulation": sorted(phase.flags) or None,
        "playwrightExitCode": playwright_code,
        "ownedApiPid": None if api is None else api.pid,
        "ownedApiExitCode": api_code,
        "stopObservation": stop_kind,
        # Bütçe aşımında "interrupted" BEKLENİR: Playwright kendi web sunucusunu
        # kapattı demektir. "forced-terminate"/"forced-kill" görülüyorsa iptal
        # zinciri bitmemiştir ve port sonraki faza öksüz devredilir; o fazın
        # WEB_PORT_BUSY'si o zaman bu satırla eşleştirilir.
        "browserStopObservation": browser_stop,
        "auditFinishExitCode": finish_code,
        "auditReconciled": accounting["reconciled"],
        "rowDamage": damage,
        "errorCode": None if passed else (error_code or accounting["code"]),
        "budgetSeconds": round(budget, 3),
        "seconds": round(time.monotonic() - phase_started, 3),
        "auditDirectory": f"audit/{phase.slug}",
        "apiLog": f"api-{phase.slug}.log",
        "playwrightLog": f"playwright-{phase.slug}.log",
        "quiescence": f"quiescence-{phase.slug}.json",
    }


def run(args: argparse.Namespace) -> int:
    repo = args.repo.resolve(strict=True)
    guard.require(
        Path(__file__).resolve() == repo / "scripts/run_owned_e2e.py"
        and Path(guard.__file__).resolve() == repo / "scripts/e2e_audit_guard.py",
        "EXECUTED_CONTROLLER_SOURCE_MISMATCH",
    )
    pins = guard.read_pins(args.pins, args.pins_sha256)
    if pins["issuer"] == "github-owned-service":
        guard.require(
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("CI") == "true",
            "GITHUB_JOB_CONTEXT_REQUIRED",
        )
    guard.require(0 < args.web_port < 65536, "WEB_PORT")
    # `nan` argparse'ın float dönüşümünden geçer, min() içinde yayılır ve
    # `nan < PHASE_FLOOR` False olduğu için taban kontrolünü de atlar; sonra
    # Popen.wait(timeout=nan) hiç zaman aşımı üretmez. Açıkça elenir.
    guard.require(
        math.isfinite(args.test_timeout) and 0 < args.test_timeout <= MAX_TEST_TIMEOUT,
        "TEST_TIMEOUT",
    )
    output = args.output
    guard.require(output.is_absolute() and output.resolve() == output, "OUTPUT_PATH")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    # Guard kendi faz dizinini parents=False ile açar, üst dizini yaratmaz. Bu
    # dizinin kipini de başka hiçbir kontrol denetlemiyor; burada ölçülür.
    audit_root = output / "audit"
    audit_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    guard.require(not audit_root.lstat().st_mode & 0o077, "PRIVATE_AUDIT_ROOT")
    before = source_hashes(repo)
    guard.private_write(output / "source-before.json", before)
    # Guard'ın kendi hesabıyla birebir aynı hedef kimliği; her fazın yakalama
    # ortamını buna karşı doğrularız.
    target_id = guard.digest(
        guard.canonical({"version": 1, "trustedPinsSha256": args.pins_sha256, "pins": pins})
    )
    started = time.monotonic()
    # Son tarih, --test-timeout ile BİRLİKTE uzar: böylece ana fazın tavanı gerçekten
    # --test-timeout olur ve simülasyon fazları payını yine de korur. ci.yml
    # --test-timeout geçirmediği için CI'da tam olarak OVERALL_BUDGET geçerlidir.
    deadline = started + max(OVERALL_BUDGET, args.test_timeout + RESERVE_TOTAL + PHASE_OVERHEAD)
    records: list[dict[str, object]] = []
    for index, phase in enumerate(PHASES):
        # Sonraki fazların duvar saati payı ve BU fazın kendi ek yükü düşülür.
        # Ek yük sayılmazsa sessizce sonraki fazın payından çıkar ve son faz
        # hiç başlamaz — bu değişikliğin var olma sebebi olan 9 vaka koşmaz.
        reserve_after = sum(later.reserve for later in PHASES[index + 1 :])
        cap = args.test_timeout if phase.budget is None else phase.budget
        budget = min(cap, deadline - time.monotonic() - reserve_after - PHASE_OVERHEAD)
        if budget < PHASE_FLOOR:
            records.append(phase_failure(phase, "PHASE_BUDGET_EXHAUSTED", budget))
            break
        try:
            records.append(run_phase(phase, args, repo, pins, output, target_id, budget))
        # Bir fazın çökmesi result.json'u tamamen yutmasın: kalan fazların ve
        # önceki fazların verdikleri yine de yazılmalı.
        except guard.GuardError as error:
            records.append(phase_failure(phase, str(error), budget))
        except Exception:
            records.append(phase_failure(phase, "OWNED_E2E_FAILED", budget))
        # Uzlaştırılmamış faz, satırlarını kimsenin raporlamadığı fazdır; guard'ın
        # `begin`i quiescence aramaz, bu yüzden sonraki faz o artığı kendi
        # baseline'ına yutar ve temiz görünürdü. Kalan fazları koşmuyoruz.
        if not records[-1]["auditReconciled"]:
            break
    after = source_hashes(repo)
    guard.private_write(output / "source-after.json", after)
    # Toplam, fazların VE'sidir: eksik faz da başarıyı düşürür. Satır hasarı
    # bugün zaten guard'ın finish çıkışını 1 yapıp fazın durumunu FAIL'e
    # çeviriyor; buradaki terim o bağı kaybedersek diye ikinci kilittir.
    damaged = any(sum(damage.values()) for record in records if (damage := row_damage(record)))
    success = (
        len(records) == len(PHASES)
        and all(record["status"] == "PASS" for record in records)
        and not damaged
        and before == after
    )
    # Düz anahtarlar TEK bir fazı yansıtır (ilk düşen, yoksa son) — fazlar arası
    # karışık bir özet, tek süreçli okuyucuyu yanıltırdı.
    lead = next((record for record in records if record["status"] != "PASS"), records[-1])
    result = {
        "version": 2,
        "status": "PASS" if success else "FAIL",
        "runId": args.run_id,
        "targetId": target_id,
        "playwrightExitCode": lead.get("playwrightExitCode"),
        "ownedApiPid": lead.get("ownedApiPid"),
        "ownedApiExitCode": lead.get("ownedApiExitCode"),
        "stopObservation": lead.get("stopObservation", "not-started"),
        "auditFinishExitCode": lead.get("auditFinishExitCode"),
        "errorCode": lead.get("errorCode"),
        "leadPhase": lead["phase"],
        "sourceUnchanged": before == after,
        "webBuild": "webpack" if args.webpack else "default",
        "seconds": round(time.monotonic() - started, 3),
        "phases": records,
        "scope": (
            "Synthetic local auth, hashing embeddings, fake model; no hosted or real-provider claim"
        ),
    }
    guard.private_write(output / "result.json", result)
    print(json.dumps(result))
    return 0 if success else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--serve-owned":
        return serve_owned(int(sys.argv[2]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--pins-sha256", required=True)
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--web-port", type=int, default=3100)
    parser.add_argument("--webpack", action="store_true")
    # Ana fazın tarayıcı bütçesi. Varsayılan 900'den 720'ye indi: tek koşu üç faza
    # bölündü ve üçünün toplamı ci.yml'nin 30 dakikalık iş sınırına sığmalı.
    #
    # 720 ÖLÇÜLDÜ VE KORUNDU. Koşu 34926253846 `PLAYWRIGHT_BUDGET_EXCEEDED`
    # verdi ama sebebi bütçenin küçüklüğü DEĞİL: api-main.log'un zaman damgaları
    # 720.3 sn'lik açıklığın 544.4 sn'sinin ≥10 sn'lik BOŞLUK olduğunu gösteriyor
    # (2 × 90 sn test zaman aşımı + 18 × ~11 sn expect zaman aşımı + kesilen
    # kuyruk). Gerçek iş yalnız 175.7 sn. Fazlama ÖNCESİ koşuda (34900228666,
    # 87 vaka) aynı hesap 182.8 sn veriyor — yani vaka başına iş 2.10 → 2.25 sn,
    # uygulama yavaşlamadı; "2,5 kat yavaşlama" tamamen düşen testlerin bekleme
    # süresidir. Yeşil bir ana fazın maliyeti ~250 sn (üç bağımsız türetme).
    # Üst sınır hesabında vaka tavanının 90 sn OLMADIĞINA dikkat: süit içinde
    # `test.setTimeout` 120_000 (14 vaka), 150_000 (5) ve 180_000 (2) ile
    # yükseltiliyor ve ana fazda `retries: 1` var, yani TEK bir asılı ağır vaka
    # 2 × 180 = 360 sn yiyebilir. Yeşil ~250 + bir asılı ağır vaka ~360 = ~610 sn,
    # hâlâ 720'nin altında; İKİ asılı ağır vaka sığmaz ve `budget` aşılır —
    # istenen işaret de budur.
    # Bu yüzden 720 BÜYÜTÜLMEDİ: büyütmek yalnız asılı kalan bir süitin daha
    # uzun yanmasını sağlar, kusuru göstermez.
    # Not: `student-exam-flow.spec.ts:259` (durationMinutes 1, expect.poll 95 sn)
    # yeşilken ~60 sn DÜRÜSTÇE bekler; iki ölçülen koşuda da 10 sn'de düştüğü
    # için bu bedel hiç ödenmedi, yeşil tahmine ayrıca eklendi.
    parser.add_argument("--test-timeout", type=float, default=720)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return run(args)
    except guard.GuardError as error:
        print(json.dumps({"status": "FAIL", "code": str(error)}))
        return 2
    except Exception:
        print(json.dumps({"status": "FAIL", "code": "OWNED_E2E_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
