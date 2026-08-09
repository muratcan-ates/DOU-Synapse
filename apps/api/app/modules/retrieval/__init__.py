"""Faz A — hibrit retrieval.

Dışarıya verilen yüzey buradan okunur; çağıranlar alt modüllere doğrudan bağlanmaz.
`HybridRetriever` `contracts.Retriever` protokolünü uygular (ham sonuç), `retrieve`
kanıt kapısını uygulayan üretim yoludur. Farkın gerekçesi `service.py`'de.
"""

from app.modules.retrieval.service import (
    HybridRetriever,
    RetrievalResult,
    fuse,
    retrieve,
)

__all__ = [
    "HybridRetriever",
    "RetrievalResult",
    "fuse",
    "retrieve",
]
