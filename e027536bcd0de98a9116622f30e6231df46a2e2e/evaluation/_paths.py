"""Depo yolları ve `app` paketinin import edilebilir hale getirilmesi.

`evaluation/` betikleri depo kökünden koşar ama `app` paketi `apps/api` altında
yaşar. Yol ekleme iki betikte de gerektiği için burada bir kez yapılır; ayrı ayrı
yazılsaydı biri güncellenip diğeri unutulurdu (Anayasa XI).

`app` import etmek DB bağlantısı açmaz — yalnız modül yükler. Ayrıştırıcı ve
ayarlar bu sayede ölçüm betiklerinden kullanılabilir; ölçümün üretimle aynı
kodu kullanması, ölçümün geçerliliğinin ön koşuludur.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
EVALUATION_ROOT = REPO_ROOT / "evaluation"
GOLD_SET_DIR = EVALUATION_ROOT / "gold_set"
RESULTS_DIR = EVALUATION_ROOT / "results"
DEFAULT_MATERIAL_DIR = REPO_ROOT / "sample_data" / "isletim-sistemleri"


def ensure_api_on_path() -> None:
    """`apps/api`'yi sys.path'e ekler (zaten varsa dokunmaz)."""
    api_path = str(API_ROOT)
    if api_path not in sys.path:
        sys.path.insert(0, api_path)
