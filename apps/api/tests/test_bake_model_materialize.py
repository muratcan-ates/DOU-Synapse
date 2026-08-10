"""`bake_embedding_model._materialize` — symlink'in gerçek dosyaya çevrilmesi.

Var oluş sebebi (PR #4, CI Docker build): onnx 1.22 harici ağırlık dosyası
(`model.onnx_data`) symlink olduğunda yüklemeyi reddediyor ve HF önbelleği
snapshot'ta tam olarak symlink tutuyor. Kusurun kendisi yalnız Docker build'de
görünür; bu test onun altındaki dönüşümü Docker'sız çiviler — biri
`_materialize` çağrılarını kaldırır ya da davranışını bozarsa burada kırmızı
yanar, imaj build'ini beklemeye gerek kalmaz.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "bake_embedding_model",
    Path(__file__).resolve().parents[1] / "scripts" / "bake_embedding_model.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_bake = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_bake)


class TestMaterialize:
    def test_symlink_gercek_dosyaya_doner_icerik_korunur(self, tmp_path: Path) -> None:
        blob = tmp_path / "blobs" / "abc123"
        blob.parent.mkdir()
        blob.write_bytes(b"onnx-agirliklari")
        link = tmp_path / "model.onnx_data"
        link.symlink_to(blob)

        _bake._materialize(link)

        assert not link.is_symlink(), "onnx 1.22'nin reddettiği şey tam olarak bu"
        assert link.read_bytes() == b"onnx-agirliklari"
        # Hardlink beklenir: aynı inode, ek disk maliyeti yok. Kopyaya düşen
        # EXDEV yolu ayrı dosya sistemi ister ve tmp_path'te üretilemez.
        assert link.stat().st_ino == blob.stat().st_ino

    def test_gercek_dosya_dokunulmadan_gecilir(self, tmp_path: Path) -> None:
        gercek = tmp_path / "model.onnx"
        gercek.write_bytes(b"zaten-gercek")
        ino_once = gercek.stat().st_ino

        _bake._materialize(gercek)

        assert gercek.read_bytes() == b"zaten-gercek"
        assert gercek.stat().st_ino == ino_once

    def test_quantize_yolu_materialize_cagiriyor(self) -> None:
        """Kaynak çivisi: `_quantize` ve `--no-quantize` yolu dönüşümü atlayamaz.

        Davranış testi yalnız yardımcıyı sınar; bu tarama, birinin çağrıları
        silmesini yakalar. Docker build'i koşturmadan verilebilecek en doğrudan
        güvence bu ikilidir.
        """
        source = (
            Path(__file__).resolve().parents[1] / "scripts" / "bake_embedding_model.py"
        ).read_text()
        assert source.count("_materialize(") >= 4, (
            "quantize + no-quantize yollarının ikisi de model.onnx ve "
            "model.onnx_data'yı gerçek dosyaya çevirmeli"
        )

    def test_cevrilemeyen_symlink_sessizce_gecilmez(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blob = tmp_path / "blob"
        blob.write_bytes(b"x")
        link = tmp_path / "model.onnx_data"
        link.symlink_to(blob)

        def bozuk_link(*args: object, **kwargs: object) -> None:
            raise OSError("EXDEV benzeri")

        def bozuk_copy(src: object, dst: object) -> None:
            Path(str(dst)).symlink_to(blob)  # kopya da symlink bırakırsa

        monkeypatch.setattr(_bake.os, "link", bozuk_link)
        monkeypatch.setattr(_bake.shutil, "copy2", bozuk_copy)

        with pytest.raises(RuntimeError, match="çevrilemedi"):
            _bake._materialize(link)
