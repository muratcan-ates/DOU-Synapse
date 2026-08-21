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
import os
from pathlib import Path

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

    def test_quantize_ve_no_quantize_yollari_cagiriyor(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "scripts" / "bake_embedding_model.py"
        ).read_text()
        assert source.count("_materialize(") >= 4, (
            "iki yol da model.onnx ve model.onnx_data'yı çevirmeli"
        )

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
