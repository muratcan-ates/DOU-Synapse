"""`measure_embedding_rss.py` çıktı sözleşmesi testleri.

Bu testler MODEL İNDİRMEZ. fastembed kolunun tamamı sentetik bir önbellek dizini
üzerinde sınanır; gerçek ölçüm yalnız `hashing` sağlayıcısıyla ve bir kez uçtan uca
koşturulur. Amaç: JSON alan adları, durum değerleri ve hata yolları sessizce
değişemesin — rapora yazılan sayıların şeması bu dosyada çivilidir.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import measure_embedding_rss as rss

SCRIPT = Path(rss.__file__).resolve()


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=rss.CHILD_TIMEOUT_SECONDS,
        check=False,
    )


# --- Saf yardımcılar --------------------------------------------------------------


def test_default_model_matches_production_provider() -> None:
    """Betik kendi model sabitini tutmaz gibi davranmamalı; üretimdekiyle aynı olmalı."""
    from app.modules.ingestion.embedding import FASTEMBED_MODEL

    assert rss.DEFAULT_MODEL == FASTEMBED_MODEL


def test_sample_texts_are_deterministic_and_sized() -> None:
    first = rss.sample_texts(5)
    assert len(first) == 5
    assert first == rss.sample_texts(5)
    assert len(set(first)) == 5
    assert all(len(text) > 100 for text in first)


def test_peak_rss_unit_is_detected_not_assumed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rss.sys, "platform", "darwin")
    assert rss.peak_rss_scale() == (1, "darwin-bayt")
    monkeypatch.setattr(rss.sys, "platform", "linux")
    assert rss.peak_rss_scale() == (1024, "posix-kilobayt")


def test_peak_rss_is_positive_and_monotonic() -> None:
    first = rss.peak_rss_bytes()
    assert first > 0
    ballast = [bytearray(1024 * 1024) for _ in range(24)]
    assert rss.peak_rss_bytes() >= first
    del ballast


def test_current_rss_reports_its_source() -> None:
    value, source = rss.current_rss()
    assert source in {"psutil", "proc", "ps", "yok"}
    if source == "yok":
        assert value is None
    else:
        assert value is not None and value > 0


def test_format_mb_uses_turkish_decimal_and_never_fakes_a_number() -> None:
    assert rss.format_mb(None) == "ölçülmedi"
    assert rss.format_mb(rss.MB) == "1,0 MB"
    assert rss.format_seconds(None) == "ölçülmedi"
    assert rss.format_seconds(0.5) == "0,500 sn"


# --- fastembed yoklaması: indirme yok ---------------------------------------------


def test_cache_dir_resolution_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path / "ortam"))
    assert rss.resolve_fastembed_cache_dir(str(tmp_path / "acik")) == tmp_path / "acik"
    assert rss.resolve_fastembed_cache_dir(None) == tmp_path / "ortam"
    monkeypatch.delenv("FASTEMBED_CACHE_PATH")
    assert rss.resolve_fastembed_cache_dir(None).name == "fastembed_cache"


def test_cache_dir_resolution_has_no_side_effect(tmp_path: Path) -> None:
    hedef = tmp_path / "yok"
    assert rss.resolve_fastembed_cache_dir(str(hedef)) == hedef
    assert not hedef.exists()


def test_find_cached_model_ignores_half_finished_download(tmp_path: Path) -> None:
    assert rss.find_cached_model(tmp_path / "olmayan", rss.DEFAULT_MODEL) is None
    assert rss.find_cached_model(tmp_path, rss.DEFAULT_MODEL) is None
    bos = tmp_path / "models--intfloat--multilingual-e5-large"
    (bos / "snapshots").mkdir(parents=True)
    assert rss.find_cached_model(tmp_path, rss.DEFAULT_MODEL) is None
    (bos / "snapshots" / "model.onnx").write_bytes(b"sahte")
    assert rss.find_cached_model(tmp_path, rss.DEFAULT_MODEL) == bos


def test_find_cached_model_accepts_fastembed_flat_layout(tmp_path: Path) -> None:
    duz = tmp_path / "fast-multilingual-e5-large"
    duz.mkdir()
    (duz / "model_optimized.onnx").write_bytes(b"sahte")
    assert rss.find_cached_model(tmp_path, rss.DEFAULT_MODEL) == duz


def test_probe_reports_missing_model_with_reason(tmp_path: Path) -> None:
    probe = rss.fastembed_probe(rss.DEFAULT_MODEL, str(tmp_path))
    assert probe["model_cached"] is False
    assert probe["cached_path"] is None
    assert probe["cache_dir"] == str(tmp_path)
    assert probe["reason"]
    assert set(probe) == {
        "importable",
        "version",
        "model",
        "cache_dir",
        "model_cached",
        "cached_path",
        "reason",
    }


# --- Alt süreç çıktısının ayrıştırılması ------------------------------------------


def test_parse_child_output_takes_the_matching_json_line() -> None:
    gurultu = "uyarı: bir şey\n"
    kayit = json.dumps({"role": "api", "status": "measured"})
    parsed = rss.parse_child_output("api", 0, gurultu + kayit + "\n", "")
    assert parsed["status"] == "measured"


def test_parse_child_output_reports_missing_json_as_error() -> None:
    parsed = rss.parse_child_output("worker", 3, "hiç JSON yok\n", "ImportError: x\nsonuncu\n")
    assert parsed["status"] == "error"
    assert "çıkış kodu 3" in parsed["error"]
    assert "sonuncu" in parsed["error"]


def test_parse_child_output_rejects_a_record_for_another_role() -> None:
    kayit = json.dumps({"role": "api", "status": "measured"})
    parsed = rss.parse_child_output("worker", 0, kayit, "")
    assert parsed["status"] == "error"


def test_child_environment_opens_dev_auth_only_without_a_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    _, overrides = rss.child_environment("hashing", "api", rss.DEFAULT_MODEL, None)
    assert overrides["DEV_AUTH_ENABLED"] == "true"
    assert overrides["EMBEDDING_PROVIDER"] == "hashing"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "x" * 32)
    _, overrides = rss.child_environment("hashing", "worker", rss.DEFAULT_MODEL, None)
    assert "DEV_AUTH_ENABLED" not in overrides


# --- Uçtan uca: yalnız hashing, yalnız bir kez ------------------------------------


def test_fastembed_without_local_model_is_not_run_not_a_download(tmp_path: Path) -> None:
    """Model yoksa betik indirmeye ÇALIŞMAZ; `not-run` döner ve çıkış kodu 0'dır."""
    result = run_cli("--provider", "fastembed", "--cache-dir", str(tmp_path), "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["measurement"]["status"] == "not-run"
    assert report["measurement"]["processes"] == {}
    assert report["measurement"]["reason"]
    assert report["fastembed"]["model_cached"] is False


def test_unknown_provider_is_an_argument_error() -> None:
    result = run_cli("--provider", "yok-boyle-bir-sey")
    assert result.returncode == 2


def test_zero_batch_is_an_argument_error() -> None:
    result = run_cli("--provider", "hashing", "--batch", "0")
    assert result.returncode == 2


def test_hashing_end_to_end_report_contract() -> None:
    """Tek gerçek ölçüm: iki rol de ayrı süreçte ölçülür, alanlar sabittir."""
    result = run_cli("--provider", "hashing", "--batch", "8", "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["schema"] == rss.SCHEMA
    assert report["batch"] == 8
    assert report["generated_at"]
    assert set(report) == {
        "schema",
        "generated_at",
        "batch",
        "platform",
        "fastembed",
        "measurement",
        "notes",
    }
    assert report["platform"]["peak_rss_unit"] in {"darwin-bayt", "posix-kilobayt"}
    assert isinstance(report["platform"]["psutil_available"], bool)
    assert report["notes"]

    measurement = report["measurement"]
    assert measurement["provider"] == "hashing"
    assert measurement["status"] == "measured", measurement
    assert set(measurement["processes"]) == set(rss.ROLES)

    pids = set()
    for role, record in measurement["processes"].items():
        assert record["status"] == "measured", record
        assert record["module"] == rss.ROLE_MODULES[role]
        assert record["provider_name"] == "hashing-v1"
        assert record["dimension"] == 1024
        assert record["vector_dimension"] == 1024
        assert record["embedded_texts"] == 8
        assert record["cold_rss_bytes"] is None or record["cold_rss_bytes"] > 0
        assert record["peak_rss_bytes"] > 0
        assert record["peak_rss_bytes"] >= record["baseline_peak_rss_bytes"]
        assert record["model_load_seconds"] >= 0.0
        assert record["embed_seconds"] >= 0.0
        pids.add(record["pid"])

    # Roller ayrı süreçlerde ölçülmeli: aynı süreçte soğuk değer zaten kirlenmiş olur.
    assert len(pids) == len(rss.ROLES)

    summary = result.stderr
    assert "Embedding bellek ölçümü" in summary
    assert "hashing" in summary
    for role in rss.ROLES:
        assert role in summary
