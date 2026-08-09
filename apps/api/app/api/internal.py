"""Dahili uçlar — yalnız altyapı çağırır, kullanıcı arayüzü çağırmaz (T049).

Router `main.py`'ye ZATEN kayıtlıdır ve bu dosya bugün hiçbir yol eklemez.
Kayıt önden yapıldı çünkü `main.py` lider dosyasıdır ve paralel oturumların
aynı iki satırı ayrı ayrı eklemesi çakışma üretirdi (00_OKU_ONCE §1 deseni).

Faz G'nin şeridi gövdeyi buraya yazar: `POST /internal/drain`, paylaşılan sırla
korunur (`Settings.worker_drain_secret`). Sır tanımlı değilse uç açılmaz —
fail-closed (Anayasa IV): korumasız bir drain ucu, dışarıdan iş kuyruğu
tetiklemeye izin verirdi.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)
