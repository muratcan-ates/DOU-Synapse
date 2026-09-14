#!/usr/bin/env python3
"""Embedding sağlayıcısının bellek (RSS) ölçümü — runbook FAZ C' / C4.

Neden var: üretim yolu `intfloat/multilingual-e5-large`'ı ONNX üzerinde CPU'da koşturur
ve dağıtım hedefi tek bir küçük VM'dir (API süreci + worker süreci yan yana). "Sığar mı"
sorusu bugüne kadar yalnız tahminle cevaplandı. Bu betik cevabı ölçüme bağlar.

Ölçülen dört değer:

* SOĞUK RSS — süreç ayakta, uygulama modülü import edildi, model HENÜZ yüklenmedi.
* SICAK RSS — model yüklendi ve `--batch` kadar metin gömüldü.
* TEPE (peak) RSS — sürecin ömrü boyunca gördüğü en yüksek RSS.
* Bunlar API ve worker rolleri için AYRI AYRI ölçülür; iki süreç aynı makinede yan yana
  koşacağı için bellek ihtiyacı ikisinin toplamıdır.

Her rol TAZE bir alt süreçte ölçülür (betik kendini `--role` ile yeniden çağırır). Aynı
süreçte ölçmek soğuk değeri kirletir: ölçen kodun kendi importları zaten bellektedir ve
`ru_maxrss` bir kez yükseldikten sonra düşmez.

Taşınabilirlik: `psutil` bu depoda kurulu DEĞİLDİR ve bu betik için bağımlılık eklenmez.
Anlık RSS sırayla psutil (varsa) → `/proc/self/status` (Linux) → `ps` (macOS/BSD)
yolundan okunur; hiçbiri yoksa değer `null` kalır ve kaynak `yok` yazılır. Tepe RSS
`resource.getrusage` ile okunur: `ru_maxrss` macOS'ta BAYT, Linux ve diğer POSIX'lerde
KİLOBAYT döndürür — birim platformdan tespit edilir, varsayılmaz.

Model İNDİRİLMEZ. `--provider fastembed` yalnız model zaten yerel önbellekteyse ölçer;
değilse ölçüm `not-run` döner ve sebebi yazılır. Ağdan ~1 GB model çekmek bir ölçüm
betiğinin işi değildir ve ölçümü yeniden üretilemez kılar.

Kullanım (depo kökünden):
    apps/api/.venv/bin/python scripts/measure_embedding_rss.py --provider hashing --json
    apps/api/.venv/bin/python scripts/measure_embedding_rss.py --provider fastembed --batch 64

Çıkış kodu: 0 ölçüm tamam ya da temiz `not-run`; 1 alt süreç çöktü; 2 argüman hatası.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

SCHEMA = "dou-embedding-rss-v1"
PROVIDERS = ("hashing", "fastembed")
# Rol → gerçekten ayağa kalkan modül. Ölçüm "bir embedding nesnesi ne kadar yer kaplar"
# sorusunu değil, "o süreç ne kadar yer kaplar" sorusunu cevaplamalı.
ROLE_MODULES = {"api": "app.main", "worker": "app.worker"}
ROLES = tuple(ROLE_MODULES)
DEFAULT_MODEL = "intfloat/multilingual-e5-large"
DEFAULT_BATCH = 32
CHILD_TIMEOUT_SECONDS = 900
MB = 1024 * 1024

# e5 çok dilli model qint8 niceleme yolunda AVX512-VNNI ister; Apple Silicon/ARM'da bu
# komut kümesi yoktur. Runbook'taki 562 MB smoke değeri x86 içindir, ARM'da ölçülemez.
_QINT8_ARCHS = ("x86_64", "amd64")


# --- Süreç belleği ---------------------------------------------------------------


def peak_rss_scale() -> tuple[int, str]:
    """`ru_maxrss` çarpanı ve birim etiketi.

    macOS bayt, diğer POSIX sistemler kilobayt döndürür. Bu fark ölçümü 1024 kat
    yanlış gösterecek kadar büyüktür, o yüzden tahmin edilmez.
    """
    if sys.platform == "darwin":
        return 1, "darwin-bayt"
    return 1024, "posix-kilobayt"


def peak_rss_bytes() -> int:
    scale, _ = peak_rss_scale()
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * scale


def _rss_from_psutil() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    return int(psutil.Process().memory_info().rss)


def _rss_from_proc() -> int | None:
    try:
        content = Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
    return None


def _rss_from_ps() -> int | None:
    ps_path = shutil.which("ps")
    if ps_path is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [ps_path, "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    if not value.isdigit():
        return None
    return int(value) * 1024


def current_rss() -> tuple[int | None, str]:
    """Anlık RSS (bayt) ve hangi kaynaktan okunduğu."""
    readers = (("psutil", _rss_from_psutil), ("proc", _rss_from_proc), ("ps", _rss_from_ps))
    for source, reader in readers:
        value = reader()
        if value is not None:
            return value, source
    return None, "yok"


# --- fastembed yoklaması (indirme YOK) -------------------------------------------


def resolve_fastembed_cache_dir(cache_dir: str | None) -> Path:
    """fastembed'in önbellek dizinini indirmeden ve dizin yaratmadan çöz.

    fastembed'in kendi `define_cache_dir` yardımcısı çağrıldığında dizini OLUŞTURUR;
    bir yoklama işlevi yan etki bırakmamalıdır. Öncelik sırası oradakiyle aynıdır:
    açık değer → `FASTEMBED_CACHE_PATH` → geçici dizin altındaki `fastembed_cache`.
    """
    if cache_dir:
        return Path(cache_dir).expanduser()
    env_value = os.environ.get("FASTEMBED_CACHE_PATH")
    if env_value:
        return Path(env_value).expanduser()
    return Path(tempfile.gettempdir()) / "fastembed_cache"


def find_cached_model(cache_dir: Path, model_name: str) -> Path | None:
    """Model yerel önbellekte mi — yalnız dosya sistemine bakar.

    İki düzen kabul edilir: HuggingFace anlık görüntüsü
    (`models--intfloat--multilingual-e5-large`) ve fastembed'in düz dizini
    (`fast-multilingual-e5-large`). Yarım kalmış indirmeyi "var" saymamak için dizinin
    içinde en az bir `.onnx` dosyası aranır.
    """
    if not cache_dir.is_dir():
        return None
    slug = model_name.split("/")[-1].casefold()
    hf_style = model_name.replace("/", "--").casefold()
    try:
        entries = sorted(cache_dir.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name.casefold()
        if (hf_style in name or slug in name) and any(entry.rglob("*.onnx")):
            return entry
    return None


def fastembed_probe(model_name: str, cache_dir: str | None) -> dict[str, Any]:
    """fastembed'in ve modelin yerel durumu. Ağa çıkmaz, dizin oluşturmaz."""
    resolved = resolve_fastembed_cache_dir(cache_dir)
    probe: dict[str, Any] = {
        "importable": False,
        "version": None,
        "model": model_name,
        "cache_dir": str(resolved),
        "model_cached": False,
        "cached_path": None,
        "reason": None,
    }
    try:
        import fastembed
    except ImportError as exc:
        probe["reason"] = f"fastembed import edilemedi: {exc}"
        return probe
    probe["importable"] = True
    probe["version"] = getattr(fastembed, "__version__", None)
    match = find_cached_model(resolved, model_name)
    probe["model_cached"] = match is not None
    probe["cached_path"] = str(match) if match is not None else None
    if match is None:
        probe["reason"] = (
            f"model yerel önbellekte yok ({resolved}); ölçüm için indirme yapılmaz"
        )
    return probe


# --- Ölçüm (alt süreçte koşar) ---------------------------------------------------


def sample_texts(batch: int) -> list[str]:
    """Deterministik ölçüm metinleri.

    Rastgele metin, ölçümü koşudan koşuya oynatır. Uzunluk gerçek bir chunk'a yakın
    tutulur ki tokenizer ve gömme maliyeti aynı büyüklük mertebesinde kalsın.
    """
    body = (
        "Bu paragraf ders materyalinden alınmış bir chunk'ı taklit eder. İçerik Türkçe ve "
        "İngilizce terimleri birlikte taşır: retrieval augmented generation, embedding "
        "space, cosine similarity, chunk sınırı, kanıt eşiği ve atıf kümesi üyeliği."
    )
    return [f"{index:04d} · {body}" for index in range(batch)]


def measure_in_process(provider_key: str, role: str, batch: int) -> dict[str, Any]:
    """Bu sürecin ölçümü. Yalnız alt süreçte çağrılır; soğuk değer buna bağlıdır."""
    import importlib

    record: dict[str, Any] = {
        "role": role,
        "module": ROLE_MODULES[role],
        "provider": provider_key,
        "pid": os.getpid(),
        "status": "error",
        "error": None,
    }
    baseline, rss_source = current_rss()
    record["rss_source"] = rss_source
    record["baseline_rss_bytes"] = baseline
    record["baseline_peak_rss_bytes"] = peak_rss_bytes()

    importlib.import_module(ROLE_MODULES[role])
    cold, _ = current_rss()
    record["cold_rss_bytes"] = cold
    record["cold_peak_rss_bytes"] = peak_rss_bytes()

    from app.modules.ingestion.embedding import get_embedding_provider, set_embedding_provider

    # Modül düzeyinde önbelleklenmiş sağlayıcı varsa ölçüm "sıcak" başlar; sıfırlanır.
    set_embedding_provider(None)
    provider = get_embedding_provider()
    record["provider_name"] = provider.name
    record["dimension"] = provider.dimension

    texts = sample_texts(batch)
    started = time.perf_counter()
    provider.embed_documents(texts[:1])  # Tembel model yüklemesini burada tetikler.
    record["model_load_seconds"] = round(time.perf_counter() - started, 3)
    loaded, _ = current_rss()
    record["loaded_rss_bytes"] = loaded
    record["loaded_peak_rss_bytes"] = peak_rss_bytes()

    started = time.perf_counter()
    vectors = provider.embed_documents(texts)
    record["embed_seconds"] = round(time.perf_counter() - started, 3)
    record["embedded_texts"] = len(vectors)
    record["vector_dimension"] = len(vectors[0]) if vectors else 0

    warm, _ = current_rss()
    record["warm_rss_bytes"] = warm
    record["peak_rss_bytes"] = peak_rss_bytes()
    if warm is not None and cold is not None:
        record["warm_minus_cold_bytes"] = warm - cold
    else:
        record["warm_minus_cold_bytes"] = None
    record["status"] = "measured"
    return record


def run_child(provider_key: str, role: str, batch: int) -> int:
    """Alt süreç girişi: tek satırlık JSON basar, ana sürece hata yutturmaz."""
    try:
        record = measure_in_process(provider_key, role, batch)
    except Exception as exc:  # noqa: BLE001 — ana sürece yapılandırılmış hata dönmeli.
        record = {
            "role": role,
            "module": ROLE_MODULES.get(role),
            "provider": provider_key,
            "pid": os.getpid(),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(record, ensure_ascii=False))
    return 0 if record["status"] == "measured" else 1


# --- Ana süreç -------------------------------------------------------------------


def parse_child_output(role: str, returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    """Alt sürecin çıktısını kayda çevir. Bozuk çıktı sessizce yutulmaz."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("role") == role:
            return record
    return {
        "role": role,
        "module": ROLE_MODULES.get(role),
        "status": "error",
        "error": (
            f"alt süreç JSON üretmedi (çıkış kodu {returncode}); "
            f"stderr son satırlar: {' | '.join(stderr.splitlines()[-3:]) or 'boş'}"
        ),
    }


def child_environment(provider_key: str, role: str, model: str, cache_dir: str | None) -> tuple[dict[str, str], dict[str, str]]:
    """Alt sürecin ortamı ve raporda gösterilecek üzerine yazmalar."""
    env = dict(os.environ)
    overrides = {"EMBEDDING_PROVIDER": provider_key, "EMBEDDING_MODEL": model}
    if cache_dir:
        overrides["EMBEDDING_CACHE_DIR"] = cache_dir
    if not env.get("SUPABASE_JWT_SECRET"):
        # Settings, `app.main` ve `app.worker` importunda ya JWT sırrı ya dev-auth ister.
        # Ölçüm makinesinde sır yoktur; sahte bir sır yazmak yerine dev yolu açılır ve
        # bu, raporda `env_overrides` altında görünür kalır.
        overrides["DEV_AUTH_ENABLED"] = "true"
    env.update(overrides)
    return env, overrides


def spawn_child(provider_key: str, role: str, batch: int, model: str, cache_dir: str | None) -> dict[str, Any]:
    env, overrides = child_environment(provider_key, role, model, cache_dir)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--role",
        role,
        "--provider",
        provider_key,
        "--batch",
        str(batch),
        "--model",
        model,
    ]
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=str(API_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "role": role,
            "module": ROLE_MODULES.get(role),
            "status": "error",
            "error": f"alt süreç {CHILD_TIMEOUT_SECONDS} saniyede bitmedi",
            "env_overrides": overrides,
        }
    record = parse_child_output(role, result.returncode, result.stdout, result.stderr)
    record["env_overrides"] = overrides
    return record


def platform_facts() -> dict[str, Any]:
    _, unit = peak_rss_scale()
    _, rss_source = current_rss()
    machine = platform.machine()
    return {
        "system": platform.system(),
        "machine": machine,
        "python": platform.python_version(),
        "peak_rss_unit": unit,
        "current_rss_source": rss_source,
        "psutil_available": _rss_from_psutil() is not None,
        "qint8_avx512_vnni_possible": machine.casefold() in _QINT8_ARCHS,
    }


def build_notes(facts: dict[str, Any], probe: dict[str, Any]) -> list[str]:
    notes = [
        f"Tepe RSS `resource.getrusage(RUSAGE_SELF).ru_maxrss` ile okundu; birim: {facts['peak_rss_unit']}.",
        f"Anlık RSS kaynağı: {facts['current_rss_source']}.",
    ]
    if not facts["psutil_available"]:
        notes.append("psutil kurulu değil; bağımlılık eklenmedi, standart kütüphane yolu kullanıldı.")
    if not facts["qint8_avx512_vnni_possible"]:
        notes.append(
            f"qint8 niceleme yolu AVX512-VNNI ister; bu makine {facts['machine']} olduğu için "
            "o yol ölçülmedi."
        )
    if not probe["model_cached"]:
        notes.append(f"fastembed modeli ölçülmedi: {probe['reason']}")
    return notes


def build_report(
    provider_key: str, batch: int, model: str, cache_dir: str | None
) -> dict[str, Any]:
    facts = platform_facts()
    probe = fastembed_probe(model, cache_dir)
    measurement: dict[str, Any] = {
        "provider": provider_key,
        "status": "not-run",
        "reason": None,
        "processes": {},
    }
    if provider_key == "fastembed" and not probe["model_cached"]:
        measurement["reason"] = probe["reason"] or "fastembed ölçümü için model yerel değil"
    else:
        processes = {
            role: spawn_child(provider_key, role, batch, model, cache_dir) for role in ROLES
        }
        measurement["processes"] = processes
        measured = [record.get("status") == "measured" for record in processes.values()]
        measurement["status"] = "measured" if all(measured) else "error"
        if not all(measured):
            measurement["reason"] = "en az bir alt süreç ölçüm üretemedi"
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "batch": batch,
        "platform": facts,
        "fastembed": probe,
        "measurement": measurement,
        "notes": build_notes(facts, probe),
    }


# --- İnsan okunur özet -----------------------------------------------------------


def format_mb(value: int | None) -> str:
    """Bayt → MB, Türkçe ondalık ayırıcıyla. Ölçülmeyen değer sayı gibi görünmez."""
    if value is None:
        return "ölçülmedi"
    return f"{value / MB:.1f}".replace(".", ",") + " MB"


def format_seconds(value: float | None) -> str:
    if value is None:
        return "ölçülmedi"
    return f"{value:.3f}".replace(".", ",") + " sn"


def render_summary(report: dict[str, Any]) -> str:
    facts = report["platform"]
    probe = report["fastembed"]
    measurement = report["measurement"]
    lines = [
        f"Embedding bellek ölçümü · {report['schema']} · {report['generated_at']}",
        (
            f"Platform: {facts['system']} {facts['machine']} · Python {facts['python']} · "
            f"anlık RSS: {facts['current_rss_source']} · tepe RSS birimi: {facts['peak_rss_unit']}"
        ),
    ]
    if probe["importable"]:
        cached = "var" if probe["model_cached"] else "yok"
        lines.append(
            f"fastembed: kurulu ({probe['version']}) · model {probe['model']} · "
            f"yerel önbellek: {cached}"
        )
    else:
        lines.append(f"fastembed: kurulu değil ({probe['reason']})")

    lines.append(f"Sağlayıcı: {measurement['provider']} · durum: {measurement['status']} · batch: {report['batch']}")
    if measurement["reason"]:
        lines.append(f"  sebep: {measurement['reason']}")
    for role in ROLES:
        record = measurement["processes"].get(role)
        if record is None:
            lines.append(f"  {role:<7} ölçülmedi")
            continue
        if record.get("status") != "measured":
            lines.append(f"  {role:<7} hata: {record.get('error')}")
            continue
        lines.append(
            f"  {role:<7} ({record['module']}) soğuk {format_mb(record['cold_rss_bytes'])} · "
            f"sıcak {format_mb(record['warm_rss_bytes'])} · "
            f"tepe {format_mb(record['peak_rss_bytes'])} · "
            f"model yükleme {format_seconds(record['model_load_seconds'])} · "
            f"{record['embedded_texts']} metin {format_seconds(record['embed_seconds'])}"
        )
    lines.append("Notlar:")
    lines.extend(f"  - {note}" for note in report["notes"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="measure_embedding_rss.py",
        description="Embedding sağlayıcısının soğuk/sıcak/tepe RSS ölçümü (API + worker).",
    )
    parser.add_argument("--provider", choices=PROVIDERS, default="hashing")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="gömülecek metin sayısı")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="fastembed model adı")
    parser.add_argument("--cache-dir", default=None, help="fastembed önbellek dizini")
    parser.add_argument("--json", action="store_true", help="stdout'a yalnız JSON yaz")
    parser.add_argument(
        "--role",
        choices=ROLES,
        default=None,
        help="iç kullanım: alt süreç bu rolü ölçüp tek satır JSON basar",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.batch < 1:
        parser.error("--batch en az 1 olmalı")

    if args.role is not None:
        return run_child(args.provider, args.role, args.batch)

    report = build_report(args.provider, args.batch, args.model, args.cache_dir)
    summary = render_summary(report)
    if args.json:
        # JSON borulanabilir kalsın diye özet stderr'a gider; ikisi birden üretilir.
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(summary, file=sys.stderr)
    else:
        print(summary)
    return 0 if report["measurement"]["status"] in ("measured", "not-run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
