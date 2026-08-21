"""Demo sorularının cevaplarını `answer_cache`'e önceden doldurur (T053).

## Ne işe yarar

Demo günü ağ giderse ya da LLM sağlayıcısı kota/erişim hatası verirse, önceden
doldurulmuş önbellek sayesinde sunum soruları LLM'e HİÇ gitmeden cevaplanır
(PLAN §6, C planı). Önbellek birebir eşleşmelidir: benzerlik araması yoktur.

## Cevaplar nasıl üretiliyor

Elle YAZILMIYOR. Betik gerçek sohbet ucunu çağırır; cevap tam hattan geçer
(retrieval → kanıt eşiği → LLM → guardrail zinciri) ve `api/chat.py::_store_cache`
onu kendi kuralıyla önbelleğe yazar. Kural tek yerde durur: yalnız `answered`
durumundaki VE atıflı cevaplar önbelleğe girer (Anayasa I ve XI). Bu betik o
kuralın bir kopyasını taşımaz — taşısaydı ikisi zamanla ayrışırdı.

Anahtar sonucu: bir soru abstention aldıysa önbelleğe GİRMEZ ve betik bunu
raporlar. Demo günü o soruyu sormak çevrimdışıyken güvenli değildir; operatörün
bunu önceden bilmesi gerekir.

## Doğrulama

Her soru iki kez sorulur. İkinci yanıtta `cached: true` görülmeliydi; görülmezse
o soru "önbelleğe girmedi" diye raporlanır. İkinci çağrı aynı oturumu kullanır,
böylece demo geçmişi tekrarlanan turlarla şişmez.

## Kullanım

    # Yerel/çevrimdışı yığın: sunucuya gerek yok, uygulama süreç içinde koşar
    uv run python scripts/fill_answer_cache.py --questions scripts/demo_questions.json

    # Çalışan bir API'ye karşı
    uv run python scripts/fill_answer_cache.py --base-url http://localhost:8023

`--questions` dosyası kodda gömülü değildir: demo senaryosu değişince kod
değişmemelidir.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_QUESTIONS = Path(__file__).with_name("demo_questions.json")


@dataclass(frozen=True, slots=True)
class Outcome:
    course_code: str
    question: str
    status: str
    citation_count: int
    cached: bool
    note: str = ""
    #: Kapsam dışı olduğu ÖNCEDEN bildirilen soru. Bunlarda beklenen sonuç
    #: önbelleğe girmemektir; sunumda "kaynak yoksa cevap yok" güvencesini
    #: göstermek için sorulurlar.
    expected_refusal: bool = False

    @property
    def ok(self) -> bool:
        if self.expected_refusal:
            # Başarı = gerçekten reddedilmiş olması. Kapsam dışı bir soru
            # cevaplanıp önbelleğe girdiyse bu bir KUSURDUR, başarı değil.
            return not self.cached and self.status in {"insufficient_context", "out_of_scope"}
        return self.cached


def _log(message: str) -> None:
    print(message, flush=True)


async def _client(base_url: str | None) -> httpx.AsyncClient:
    """Çalışan bir API'ye ya da süreç içi uygulamaya bağlanır.

    Süreç içi biçim çevrimdışı yığın için önemlidir: konteynerde ayrıca bir
    sunucu ayağa kaldırmadan, `docker compose run` ile önbellek doldurulabilir.
    """
    if base_url:
        return httpx.AsyncClient(base_url=base_url, timeout=120.0)

    from app.main import create_app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()),
        base_url="http://demo.local",
        timeout=120.0,
    )


async def _resolve_course(
    client: httpx.AsyncClient, headers: dict[str, str], code: str
) -> str | None:
    response = await client.get("/courses", headers=headers)
    response.raise_for_status()
    for course in response.json():
        if course["code"] == code:
            course_id: str = course["id"]
            return course_id
    return None


async def _ask(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    course_id: str,
    question: str,
    session_id: str | None = None,
    *,
    rate_limit_wait: float = 61.0,
    attempts: int = 4,
) -> dict[str, Any]:
    """Bir soru sorar; kullanıcı sınırına takılırsa bekleyip yeniden dener.

    Neden gerekli: sohbet ucu kullanıcı başına kayan pencereyle sınırlı
    (`chat_rate_limit_requests`, varsayılan 20/60 sn) ve bu betik tek kullanıcı
    olarak her soruyu İKİ kez sorar. On sorudan sonra sınır kaçınılmaz biçimde
    devreye girer — 9 Ağustos'ta ilk koşuda 16 sorunun altısı 429 aldı. Sınırı
    gevşetmek yerine beklemek doğrusu: sınır üretimde de var, betik onu
    baypas etmemeli, ona uymalı.
    """
    payload: dict[str, Any] = {"question": question, "mode": "qa"}
    if session_id:
        payload["session_id"] = session_id

    for attempt in range(attempts):
        response = await client.post(f"/courses/{course_id}/chat", json=payload, headers=headers)
        if response.status_code != 429:
            response.raise_for_status()
            body: dict[str, Any] = response.json()
            return body
        if attempt == attempts - 1:
            response.raise_for_status()
        _log(f"    sınıra takıldı, {rate_limit_wait:.0f} sn bekleniyor…")
        await asyncio.sleep(rate_limit_wait)

    raise RuntimeError("ulaşılamaz")  # pragma: no cover


async def _fill_course(
    client: httpx.AsyncClient, entry: dict[str, Any], rate_limit_wait: float
) -> list[Outcome]:
    code = entry["code"]
    token = entry.get("token") or f"dev:{entry['as_user_id']}"
    headers = {"Authorization": f"Bearer {token}"}

    course_id = await _resolve_course(client, headers, code)
    if course_id is None:
        return [
            Outcome(
                code,
                "-",
                "ders_bulunamadi",
                0,
                False,
                "kullanıcı bu derse üye değil ya da ders yok",
            )
        ]

    outcomes: list[Outcome] = []
    plan = [(question, False) for question in entry.get("questions", [])]
    plan += [(question, True) for question in entry.get("out_of_scope_questions", [])]

    for question, expected_refusal in plan:
        try:
            first = await _ask(
                client, headers, course_id, question, rate_limit_wait=rate_limit_wait
            )
        except httpx.HTTPStatusError as exc:
            outcomes.append(
                Outcome(
                    course_code=code,
                    question=question,
                    status=f"http_{exc.response.status_code}",
                    citation_count=0,
                    cached=False,
                    note=exc.response.text[:200],
                    expected_refusal=expected_refusal,
                )
            )
            continue

        # İkinci tur aynı oturumda: `cached` alanı gerçekten önbellekten mi
        # geldiğini söyleyen tek kanıttır. Kapsam dışı sorularda ikinci tura
        # gerek yok — önbelleğe girmemesi zaten beklenen sonuç, ve boşuna
        # sorulan her istek kullanıcı sınırından yer yer.
        cached = False
        if not expected_refusal:
            second = await _ask(
                client,
                headers,
                course_id,
                question,
                session_id=first["session_id"],
                rate_limit_wait=rate_limit_wait,
            )
            cached = bool(second.get("cached"))

        if expected_refusal:
            note = (
                "" if first["status"] != "answered" else "BEKLENMEDİK: kapsam dışı soru cevaplandı"
            )
        else:
            note = "" if cached else "önbelleğe girmedi (abstention ya da atıfsız)"

        outcomes.append(
            Outcome(
                course_code=code,
                question=question,
                status=first["status"],
                citation_count=len(first.get("citations", [])),
                cached=cached,
                note=note,
                expected_refusal=expected_refusal,
            )
        )
    return outcomes


async def run(args: argparse.Namespace, spec: dict[str, Any]) -> list[Outcome]:
    """Soruları koşturur ve sonuçları döndürür.

    Dosya okuma/yazma bilerek dışarıda: eşzamanlı `pathlib` çağrısı olay
    döngüsünü bloklar (ruff ASYNC240) ve büyük bir raporda bu fark edilir.
    """
    client = await _client(args.base_url)

    outcomes: list[Outcome] = []
    try:
        for entry in spec["courses"]:
            outcomes.extend(await _fill_course(client, entry, args.rate_limit_wait))
    finally:
        await client.aclose()

    demo = [outcome for outcome in outcomes if not outcome.expected_refusal]
    refusals = [outcome for outcome in outcomes if outcome.expected_refusal]
    missed = [outcome for outcome in demo if not outcome.ok]

    _log("")
    _log(f"önbelleğe giren: {sum(1 for o in demo if o.ok)}/{len(demo)}")
    for outcome in demo:
        mark = "✓" if outcome.ok else "✗"
        _log(
            f"  {mark} [{outcome.course_code}] {outcome.status:<20} "
            f"atıf={outcome.citation_count}  {outcome.question[:60]}"
        )
        if outcome.note:
            _log(f"      → {outcome.note}")

    if refusals:
        _log("")
        _log(
            f"kapsam dışı (reddetmesi BEKLENEN): {sum(1 for o in refusals if o.ok)}/{len(refusals)}"
        )
        for outcome in refusals:
            mark = "✓" if outcome.ok else "✗"
            _log(f"  {mark} [{outcome.course_code}] {outcome.status:<20} {outcome.question[:60]}")
            if outcome.note:
                _log(f"      → {outcome.note}")

    if missed:
        _log("")
        _log(
            "UYARI: yukarıdaki ✗ soruları çevrimdışı demoda LLM'e gitmek zorunda "
            "kalır. Ağsız provada bu soruları sormayın ya da materyali güçlendirin."
        )
    if any(not outcome.ok for outcome in refusals):
        _log("")
        _log(
            "UYARI: kapsam dışı olması beklenen bir soru reddedilmedi. Sunumda "
            "'kaynak yoksa cevap yok' iddiasını bu soruyla göstermeyin."
        )

    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument(
        "--base-url",
        default=None,
        help="çalışan API adresi; verilmezse uygulama süreç içinde koşar",
    )
    parser.add_argument("--report", type=Path, help="sonucu JSON olarak yaz")
    parser.add_argument(
        "--rate-limit-wait",
        type=float,
        default=61.0,
        help="429 alınca beklenecek saniye (sunucudaki pencereden biraz uzun olmalı)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="önbelleğe girmeyen soru varsa sıfırdan farklı dön",
    )
    args = parser.parse_args()

    spec = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    outcomes = asyncio.run(run(args, spec))

    if args.report:
        Path(args.report).write_text(
            json.dumps([asdict(outcome) for outcome in outcomes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Varsayılan çıkış kodu 0: eksik önbellek bir betik hatası değil, bir demo
    # riskidir ve raporlanır. `--strict` onu CI kapısına çevirir.
    failed = [outcome for outcome in outcomes if not outcome.ok]
    return 1 if (failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
