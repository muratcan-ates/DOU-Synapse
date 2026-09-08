"""`bake_embedding_model._materialize` — tek bağlantılı gerçek inode sözleşmesi.

onnx 1.22 harici ağırlık dosyasında symlink'i VE birden çok hardlink taşıyan
dosyayı reddediyor (PR #4 CI: ilk koşu symlink'i, ikincisi bu yardımcının
hardlink kullanan ilk sürümünü yakaladı — "potential hardlink attack"). Bu
testler mekanizmayı değil SÖZLEŞMEYİ çiviler: çıktıda `islink == False` ve
`st_nlink == 1`. Kusur yalnız Docker build'de görünür; bu dosya onu Docker'sız
kırmızıya çevirebilen tek yerdir.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "bake_embedding_model",
    Path(__file__).resolve().parents[1] / "scripts" / "bake_embedding_model.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_bake = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_bake)


def _tek_baglantili_gercek(path: Path) -> bool:
    return not path.is_symlink() and path.lstat().st_nlink == 1


class TestMaterialize:
    def test_symlink_tek_baglantili_gercek_dosyaya_doner(self, tmp_path: Path) -> None:
        blob = tmp_path / "blobs" / "abc123"
        blob.parent.mkdir()
        blob.write_bytes(b"onnx-agirliklari")
        link = tmp_path / "model.onnx_data"
        link.symlink_to(blob)

        _bake._materialize(link)

        assert _tek_baglantili_gercek(link), "onnx'in kabul ettiği tek biçim bu"
        assert link.read_bytes() == b"onnx-agirliklari"

    def test_hardlinkli_dosya_bagi_koparilir(self, tmp_path: Path) -> None:
        """İlk sürümün ürettiği durumun regresyonu: nlink>1 → 'hardlink attack'."""
        dosya = tmp_path / "model.onnx_data"
        dosya.write_bytes(b"agirliklar")
        os.link(dosya, tmp_path / "ikinci-bag")
        assert dosya.stat().st_nlink == 2

        _bake._materialize(dosya)

        assert _tek_baglantili_gercek(dosya)
        assert dosya.read_bytes() == b"agirliklar"

    def test_zaten_tek_baglantili_dosya_dokunulmaz(self, tmp_path: Path) -> None:
        gercek = tmp_path / "model.onnx"
        gercek.write_bytes(b"zaten-gercek")
        ino = gercek.stat().st_ino

        _bake._materialize(gercek)

        assert gercek.stat().st_ino == ino, "gereksiz kopya, gereksiz disk"
        assert gercek.read_bytes() == b"zaten-gercek"

    @pytest.mark.parametrize("no_quantize", [False, True], ids=["int8", "fp32"])
    def test_quantize_ve_no_quantize_yollari_cagiriyor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_quantize: bool
    ) -> None:
        """Gerçek CLI dalları ONNX okuyucusuna iki güvenli dosya teslim etmeli."""
        cache = tmp_path / "cache"
        snapshot = cache / "models--test" / "snapshots" / "revision"
        blobs = cache / "models--test" / "blobs"
        snapshot.mkdir(parents=True)
        blobs.mkdir()
        payloads = {"model.onnx": b"model-graph", "model.onnx_data": b"external-weights"}
        for name, payload in payloads.items():
            blob = blobs / name
            blob.write_bytes(payload)
            (snapshot / name).symlink_to(blob)
        report = tmp_path / "report.json"
        arguments = ["bake", "--cache-dir", str(cache), "--skip-download", "--report", str(report)]
        if no_quantize:
            arguments.append("--no-quantize")
        monkeypatch.setattr(sys, "argv", arguments)
        quantize_calls: list[dict[str, Any]] = []
        embed_calls: list[bool] = []

        def assert_materialized_inputs() -> None:
            for name, payload in payloads.items():
                path = snapshot / name
                assert _tek_baglantili_gercek(path), f"ONNX için güvenli değil: {name}"
                assert path.read_bytes() == payload

        def fake_quantize_dynamic(**kwargs: Any) -> None:
            assert_materialized_inputs()
            assert kwargs["model_input"] == snapshot / "model.onnx"
            quantize_calls.append(kwargs)
            kwargs["model_output"].write_bytes(b"int8")

        def fake_embed(cache_dir: Path, model_name: str) -> list[list[float]]:
            assert cache_dir == cache
            assert model_name == "intfloat/multilingual-e5-large"
            if no_quantize:
                assert_materialized_inputs()
            elif embed_calls:
                assert _tek_baglantili_gercek(snapshot / "model.onnx")
                assert (snapshot / "model.onnx").read_bytes() == b"int8"
                assert not (snapshot / "model.onnx_data").exists()
            embed_calls.append(no_quantize)
            return [[1.0, float(index + 1)] for index in range(len(_bake.PROBE_TEXTS))]

        def unexpected_download(*args: Any, **kwargs: Any) -> None:
            pytest.fail("Bu regresyon testi model indirmemeli")

        quantization = ModuleType("onnxruntime.quantization")
        quantization.QuantType = type("QuantType", (), {"QInt8": "QInt8"})
        quantization.quantize_dynamic = fake_quantize_dynamic
        monkeypatch.setitem(sys.modules, "onnxruntime.quantization", quantization)
        monkeypatch.setattr(_bake, "_embed", fake_embed)
        monkeypatch.setattr(_bake, "_download", unexpected_download)

        assert _bake.main() == 0
        assert len(quantize_calls) == (0 if no_quantize else 1)
        assert len(embed_calls) == (1 if no_quantize else 2)
        result = json.loads(report.read_text())
        assert result["fp32_bytes"] == sum(len(payload) for payload in payloads.values())
        if no_quantize:
            assert result["quantized"] is False
        else:
            assert result["int8_bytes"] == 4
            assert result["cosine_min"] == 1.0

    def test_sozlesme_saglanamazsa_sessizce_gecilmez(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blob = tmp_path / "blob"
        blob.write_bytes(b"x")
        os.link(blob, tmp_path / "bag2")  # nlink=2 → taşıma yolu kopyaya düşmeli
        link = tmp_path / "model.onnx_data"
        link.symlink_to(blob)

        def bozuk_copyfile(src: object, dst: object) -> None:
            os.link(blob, str(dst))  # kopya yerine yine hardlink bırakan sabotaj

        monkeypatch.setattr(_bake.shutil, "copyfile", bozuk_copyfile)

        with pytest.raises(RuntimeError, match="çevrilemedi"):
            _bake._materialize(link)
