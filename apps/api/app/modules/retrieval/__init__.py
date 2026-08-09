"""Faz A — hibrit retrieval.

Dışarıya verilen yüzey buradan okunur; çağıranlar alt modüllere doğrudan bağlanmaz.
`HybridRetriever` `contracts.Retriever` protokolünü uygular (ham sonuç), `retrieve`
kanıt kapısını uygulayan üretim yoludur. Farkın gerekçesi `service.py`'de.

`assess_evidence` kapının kararını ve **kararın sebebini** üretir; kapıyı kendi
elleriyle kuran çağıranlar (bugün `app/api/chat.py`) bu fonksiyonu çağırır, eşiği
tekrar yorumlamaz. Gerekçe ve kalibrasyon `scope.py`'de.
"""

from app.modules.retrieval.scope import (
    EvidenceLevel,
    EvidenceVerdict,
    assess_evidence,
    lexical_coverage,
)
from app.modules.retrieval.service import (
    HybridRetriever,
    RetrievalResult,
    fuse,
    retrieve,
)

__all__ = [
    "EvidenceLevel",
    "EvidenceVerdict",
    "HybridRetriever",
    "RetrievalResult",
    "assess_evidence",
    "fuse",
    "lexical_coverage",
    "retrieve",
]
