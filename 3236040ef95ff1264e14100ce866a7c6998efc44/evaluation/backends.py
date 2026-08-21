"""Ölçüm koşusunun bağlandığı iki arka uç: retrieval katmanı ve uçtan uca sohbet.

Neden bu dosya var: `evaluate.py` metrikleri hesaplar, arka uçları TANIMAZ. Retrieval
modülü Şerit 1'in, sohbet ucu Şerit 3'ün elinde ve ikisi de paralel yazılıyor.
Bağlanma noktası tek bir dosyada toplanınca, imzalar netleştiğinde düzeltilecek yer
de tek oluyor.

İki kural:

1. **Mock yok.** Retrieval katmanı gerçek veritabanı ve gerçek indeks üzerinde koşar
   (brief §Teslimat 4). Sahte bir retriever üzerinde ölçülen Recall hiçbir şey
   söylemez.
2. **Sessiz düşme yok.** Bağlanılacak fonksiyon bulunamazsa koşu, nereye baktığını
   tek tek yazarak durur. Boş sonuç döndürüp metriği %0 göstermek, saatlerce
   "retrieval kötü" diye aranan bir hataya dönüşürdü.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from _paths import ensure_api_on_path


class BackendUnavailable(RuntimeError):
    """Aranan modül/fonksiyon henüz yok. Mesaj nereye bakıldığını içerir."""


@dataclass(frozen=True, slots=True)
class RetrievedItem:
    """Arka uçtan dönen tek sonuç — `contracts.RetrievedChunk`'ın ölçüme yeten kısmı.

    Skorlar ayrı taşınır çünkü kanıt kapısı yalnız `dense_score`'a bakar
    (`service.retrieve`). Eşik kalibrasyonu (T043) tam olarak bu sayının dağılımını
    ister ve LLM'e hiç gitmeden yapılabilir.
    """

    chunk_id: str | None
    file_name: str
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    text: str
    dense_score: float = 0.0
    fts_score: float = 0.0
    fused_score: float = 0.0


#: Aday giriş noktaları, tercih sırasıyla.
#:
#: Hibritte `HybridRetriever` (yani `contracts.Retriever` protokolünün uygulaması)
#: ÖNCE denenir, `service.retrieve` sonra. Gerekçe: `retrieve` kanıt kapısını uygular
#: ve eşiğin altında kalan sorguda `chunks=[]` döner. Ölçüm katmanının işi arama
#: kalitesini ölçmek; kalibre EDİLMEMİŞ bir eşikle Recall ölçmek, retrieval'ı eşiğin
#: kusuru yüzünden kötü gösterirdi. Kapının kararı ayrıca ve her eşik için
#: hesaplanıyor (evaluate.py, eşik taraması) — kaydedilen dense skorlardan.
RETRIEVAL_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "hybrid": (
        "app.modules.retrieval.service:HybridRetriever",
        "app.modules.retrieval.service:retrieve",
        "app.modules.retrieval.service:search",
        "app.modules.retrieval.service:hybrid_search",
        "app.modules.retrieval:retrieve",
        "app.modules.retrieval:search",
    ),
    "dense": (
        "app.modules.retrieval.dense:search",
        "app.modules.retrieval.dense:dense_search",
        "app.modules.retrieval.service:dense_search",
        "app.modules.retrieval:dense_search",
    ),
}

#: Çağrılacak fonksiyonun parametre adları önceden bilinemiyor; anlamına göre eşlenir.
_PARAMETER_ALIASES: dict[str, tuple[str, ...]] = {
    "session": ("session", "db", "connection", "conn"),
    "course_id": ("course_id", "course"),
    "query": ("query", "question", "text", "q"),
    "limit": ("limit", "k", "top_k", "final_k", "n"),
}


def _resolve(path: str) -> Any:
    module_name, _, attribute = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def resolve_retrieval_callable(mode: str) -> tuple[Any, str]:
    """Verilen mod için çağrılabilir bir retrieval fonksiyonu bulur."""
    ensure_api_on_path()
    attempted: list[str] = []
    for path in RETRIEVAL_ENTRY_POINTS[mode]:
        attempted.append(path)
        try:
            return _resolve(path), path
        except (ImportError, AttributeError):
            continue
    raise BackendUnavailable(
        f"'{mode}' modu için retrieval fonksiyonu bulunamadı. Bakılan yerler:\n  "
        + "\n  ".join(attempted)
        + "\n\nŞerit 1 (retrieval) henüz main'e inmemiş olabilir. İnmişse `git fetch "
        "origin && git rebase origin/main` sonrası tekrar deneyin; imza farklıysa "
        "backends.py'deki RETRIEVAL_ENTRY_POINTS listesine gerçek yolu ekleyin."
    )


def _build_arguments(
    function: Any, *, session: Any, course_id: UUID, query: str, limit: int
) -> dict[str, Any]:
    """Fonksiyonun imzasına bakarak argümanları adlarına göre eşler.

    İmza tahmin edilmiyor, OKUNUYOR. Sabit bir çağrı biçimi yazılsaydı Şerit 1'in
    parametre adını değiştirmesi koşuyu sessizce değil ama anlaşılmaz biçimde
    kırardı; burada eksik parametre açıkça raporlanır.
    """
    available = {"session": session, "course_id": course_id, "query": query, "limit": limit}
    parameters = inspect.signature(function).parameters
    arguments: dict[str, Any] = {}
    for role, aliases in _PARAMETER_ALIASES.items():
        for alias in aliases:
            if alias in parameters:
                arguments[alias] = available[role]
                break
    missing = [
        name
        for name, parameter in parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and name not in arguments
    ]
    if missing:
        raise BackendUnavailable(
            f"{function.__module__}.{function.__qualname__} imzasındaki zorunlu "
            f"parametreler eşlenemedi: {missing}. backends.py'deki _PARAMETER_ALIASES "
            "eşlemesine ekleyin."
        )
    return arguments


def _normalize(results: Any) -> list[RetrievedItem]:
    """Farklı dönüş biçimlerini tek şekle indirger.

    Sarmalayıcı bir sonuç nesnesi (ör. `.chunks` taşıyan bir dataclass) da kabul
    edilir: eşik altında kalan sorgular için abstention bilgisini taşıyan bir zarf
    döndürmek makul bir tasarım ve ölçüm bunu engellememeli.
    """
    if results is None:
        return []
    if not isinstance(results, Sequence | list | tuple):
        for attribute in ("chunks", "results", "items"):
            inner = getattr(results, attribute, None)
            if inner is not None:
                results = inner
                break
        else:
            raise BackendUnavailable(
                f"Retrieval sonucu anlaşılamadı: {type(results)!r}. Liste ya da "
                "`chunks`/`results`/`items` alanı taşıyan bir nesne bekleniyordu."
            )

    normalized: list[RetrievedItem] = []
    for result in results:
        chunk_id = getattr(result, "chunk_id", None) or getattr(result, "id", None)
        normalized.append(
            RetrievedItem(
                chunk_id=str(chunk_id) if chunk_id else None,
                file_name=getattr(result, "file_name", ""),
                page_number=getattr(result, "page_number", None),
                slide_number=getattr(result, "slide_number", None),
                section_title=getattr(result, "section_title", None),
                text=getattr(result, "text", ""),
                dense_score=float(getattr(result, "dense_score", 0.0) or 0.0),
                fts_score=float(getattr(result, "fts_score", 0.0) or 0.0),
                fused_score=float(getattr(result, "fused_score", 0.0) or 0.0),
            )
        )
    return normalized


class RetrievalBackend:
    """`--layer retrieval`: LLM'e hiç gitmez, yalnız arama hattını ölçer.

    Ucuz ve hızlı olması tasarım gereği: eşik ve parametre denemeleri bu katmanda
    istenildiği kadar tekrarlanabilsin, kota yalnız uçtan uca koşuda harcansın.
    """

    def __init__(self, mode: str, *, as_user: UUID, top_k: int) -> None:
        self._callable, self.entry_point = resolve_retrieval_callable(mode)
        self._as_user = as_user
        self._top_k = top_k
        self.mode = mode

    @property
    def calls_llm(self) -> bool:
        return False

    async def run(self, question: str, course_id: UUID) -> list[RetrievedItem]:
        ensure_api_on_path()
        from app.core.db import rls_session

        async with rls_session(self._as_user) as session:
            if inspect.isclass(self._callable):
                # `contracts.Retriever` protokolünü uygulayan sınıf: oturumu
                # kurucuda alır, aramayı `search` yapar. İmzası sözleşmede sabit
                # olduğu için burada tahmine gerek yok.
                result = await self._callable(session).search(
                    course_id=course_id, query=question, limit=self._top_k
                )
            else:
                arguments = _build_arguments(
                    self._callable,
                    session=session,
                    course_id=course_id,
                    query=question,
                    limit=self._top_k,
                )
                result = self._callable(**arguments)
                if inspect.isawaitable(result):
                    result = await result
        return _normalize(result)


class ChatBackendProtocol(Protocol):
    async def ask(self, question: str, course_id: UUID, *, mode: str) -> dict[str, Any]: ...


class ChatBackend:
    """`--layer e2e`: HTTP ile gerçek sohbet ucu.

    Uçtan uca metrikler mutlaka GERÇEK guardrail zincirinden geçmiş cevaplar üzerinde
    ölçülür; üretim fonksiyonlarını doğrudan çağırmak zinciri atlamayı kolaylaştırır
    ve ölçülen şey kullanıcının gördüğü şey olmaktan çıkar.

    Sözleşme (Şerit 3, `app/api/chat.py`):
        POST /courses/{course_id}/chat
        {"message": str, "mode": "qa"|"socratic"|"exam", "session_id": uuid|null}
        -> {"status", "answer", "citations": [{"chunk_id", "file_name", "location"}], ...}
    """

    def __init__(self, base_url: str, token: str, *, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client: Any = None

    @property
    def calls_llm(self) -> bool:
        return True

    async def __aenter__(self) -> ChatBackend:
        import httpx

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def ask(self, question: str, course_id: UUID, *, mode: str = "qa") -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("ChatBackend `async with` bloğu içinde kullanılır.")
        response = await self._client.post(
            f"/courses/{course_id}/chat", json={"message": question, "mode": mode}
        )
        if response.status_code == 404:
            raise BackendUnavailable(
                f"POST {self.base_url}/courses/{course_id}/chat bulunamadı (404). "
                "Sohbet ucu (Şerit 3, T019) henüz inmemiş olabilir; API'nin bu "
                "branch'te çalıştığından da emin olun."
            )
        # 429 ve 5xx çağırana bırakılır: yeniden deneme ve backoff kararı kuyruğundur,
        # tek bir isteğin değil.
        response.raise_for_status()
        return dict(response.json())
