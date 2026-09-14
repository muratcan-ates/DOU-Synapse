#!/usr/bin/env python3
"""E3'ün ÇEVRİMDIŞI yarısı: kabul paketini tekrar üretilebilir üretir ve skorlar.

Neden ayrı bir dosya var. `prepare_packet.py` paketi hazırlar ama ürettiği manifest
`prepared_at`, `candidate_sha` ve `candidate_dirty` taşır; üçü de çalışma anına ve
git durumuna bağlıdır, dolayısıyla aynı girdiyle iki kez koşulduğunda çıktı bayt
bayt aynı olmaz. Ayrıca o betikte hiçbir ÖRNEKLEME yoktur: `assessment_cases.json`
içindeki bütün vakalar olduğu gibi kopyalanır. Bu yüzden "paket yeniden üretilebilir
mi", "etiketleyiciye verilen form cevabı sızdırıyor mu" ve "iki etiketleyicinin
uyumu ne" soruları bugün hiç ölçülmüyor. Bu modül yalnız o üç soruyu ölçer.

`prepare_packet.py` DEĞİŞTİRİLMEDİ. Onun işi kaynak/goldset özetlerini aday SHA'sına
bağlamak; bu modülün işi aynı taslaktan saatten ve git durumundan bağımsız bir
etiketleme paketi üretmek. Farklı sorulara cevap verdikleri için ayrı dururlar ve
ikisi de aynı `assessment_cases.json` dosyasını okur.

## "Tekrar üretilebilir" burada ne demek

Bu paketin baytları yalnız üç girdiden türer: vaka dosyasının içeriği, atıf yapılan
kaynak materyal dosyalarının içeriği ve tohum. Zaman damgası, git SHA'sı, dosya
sistemi sırası ya da sözlük sırası çıktıya girmez. Bu yüzden `--verify` gerçek bir
kapıdır: diskteki paket ile yeniden üretilen paket bayt olarak karşılaştırılabilir.
Manifeste `prepared_at` konsaydı `--verify` her koşuda "fark var" derdi ve hiçbir
şey ölçmezdi. Zaman damgası koşunun kaydına aittir, paketin kendisine değil.

## Etiketleyiciye cevabı sızdırmama

`assessment_cases.json` her öğrenci cevabının yanında `anchor` alanını taşır:
`correct`, `partial`, `incorrect`. Bu alan CEVAP ANAHTARIDIR. Etiketleyiciye verilen
Markdown formunda görünürse etiketleme bir ölçüm olmaktan çıkar, anahtarın
kopyalanmasına döner ve ortaya çıkan uyum sayısı insanların rubriği nasıl okuduğunu
değil, kopyalamayı ölçer. Bu yüzden paket ikiye ayrılır: `packet.json` ve iki etiket
formu çıpayı hiç içermez; çıpalar yalnız `answer_key.json` içindedir ve o dosya
etiketleyiciye verilmez.

Aynı gerekçeyle vakalardaki insan alanları (`expected_score`, `human_expected_score`,
`human_approved_by`, `observed_response`, ...) BOŞ olmalıdır. Doluysa bu modül paketi
üretmez ve hata verir. Sessizce boşaltmak, birinin gerçekten doldurduğu bir kararı
kaybetmek olurdu; sessizce kabul etmek ise etiketleyiciye beklenen puanı göstermek
olurdu. İkisi de yanlış, o yüzden fail-closed reddedilir.

## Bu modül E3'ü BİTİRMEZ

E3 için ≥25 GERÇEK cevap ve iki BAĞIMSIZ insan etiketleyici gerekir. Bu depoda gerçek
sağlayıcı anahtarı yok ve iki etiketleyicili bir oturum yapılmadı. Buradaki uzlaştırma
yolu, etiket dosyaları DOLDURULDUĞUNDA uyumun nasıl hesaplanacağını sabitler; etiket
üretmez, insan yerine karar vermez ve ürettiği rapor `reportable: false` damgasıyla
çıkar. Paketin kendisi de `real_provider_quality` ve `independent_human_review`
alanlarını `pending` yazar — `prepare_packet.py` ile aynı sözcükler, çünkü iki
artefaktı okuyan kişi aynı kelimeyi iki anlamda okumak zorunda kalmamalı.

Yalnız standart kütüphane ve depo içi saf modüller kullanılır: yeni bağımlılık yok,
veritabanı yok, ağ yok, sağlayıcı yok.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
REPO_ROOT = EVALUATION.parent
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

import metrics
from faithfulness import score_labels
from goldset import SourceSpec

DEFAULT_CASES = HERE / "assessment_cases.json"
DEFAULT_MATERIAL_DIR = REPO_ROOT / "sample_data" / "isletim-sistemleri"

#: Tohum sabit ve YAZILI: örneklemin nasıl seçildiği yeniden üretilebilmeli.
#: `pull_sample.py` ile aynı duruş, farklı değer — iki farklı örneklem aynı
#: tohumu paylaşırsa hangi koşudan bahsedildiği karışır.
DEFAULT_SEED = 20260914

#: E3 kabul ölçütü: en az 25 örnek. Varsayılan boyut bilerek tam bu sayıdır, çünkü
#: daha küçük bir varsayılan "koştu, geçti" izlenimi verip ölçütü sessizce düşürürdü.
E3_MINIMUM_EXAMPLES = 25
DEFAULT_SIZE = E3_MINIMUM_EXAMPLES

#: Taslaktaki çıpa adlarının etiket ölçeğindeki karşılığı. Çıpa etiketleyiciye
#: GÖSTERİLMEZ; bu eşleme yalnız etiketler geldikten sonra "insan çıpayla aynı
#: şeyi mi söyledi" hesabı için kullanılır.
ANCHOR_LABELS: dict[str, str] = {
    "correct": "doğru",
    "partial": "kısmen",
    "incorrect": "yanlış",
}

#: Etiket ölçeği üç değerlidir ve SIRALIDIR; ara değer üretilmez.
LABEL_VALUES: tuple[str, ...] = ("doğru", "kısmen", "yanlış")

#: Sıralı ölçeğin tamsayı karşılığı. Ağırlıklı kappa mesafeyi puan değerinden
#: hesapladığı için bu eşleme rapora da yazılır: okuyan "2 neydi" diye sormasın.
LABEL_SCORES: dict[str, int] = {"yanlış": 0, "kısmen": 1, "doğru": 2}

#: Vaka düzeyinde insanın dolduracağı alanlar — pakette BOŞ olmak zorunda.
BLANK_CASE_FIELDS: tuple[str, ...] = (
    "human_approved_by",
    "human_approved_at",
    "expected_score",
    "expected_missing_points",
    "observed_response",
)

#: Öğrenci cevabı düzeyinde insanın dolduracağı alan.
BLANK_ANSWER_FIELDS: tuple[str, ...] = ("human_expected_score",)

#: Vakanın koşu durumu. `not_run` dışında bir değer, koşulmamış bir sonucun
#: koşulmuş gibi yazıldığı anlamına gelir.
REQUIRED_RESULT = "not_run"

PACKET_FILE = "packet.json"
ANSWER_KEY_FILE = "answer_key.json"
LABEL_FILES = ("labels_etiketleyici_1.md", "labels_etiketleyici_2.md")
CHECKSUM_FILE = "SHA256SUMS"

PACKET_KIND = "acceptance_packet_offline"
ANSWER_KEY_KIND = "acceptance_answer_key"
REPORT_KIND = "acceptance_label_agreement"

PACKET_WARNING = (
    "Çevrimdışı üretilmiş etiketleme paketidir. Gerçek sağlayıcı koşusu yapılmadı ve "
    "iki bağımsız insan etiketlemesi alınmadı; bu paket tek başına kalite kanıtı değildir."
)


class PacketError(ValueError):
    """Paket girdisi ya da diskteki paket, kanıt üretmeye uygun değil.

    Ayrı bir tip: CLI bu hatayı yakalayıp Türkçe tek satır basar ve 2 döner.
    Beklenmeyen bir `TypeError`/`KeyError` ise yığın izi ile görünür kalmalı —
    ikisini aynı kutuya koymak, kodun kendi hatasını "girdi bozuk" diye
    raporlamasına yol açardı.
    """


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise PacketError(f"Kaynak dosya okunamadı: {path}: {exc}") from exc


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Sözlüğü bayt bayt kararlı JSON'a çevirir.

    `ensure_ascii=False`: Türkçe metin kaçış dizisine dönüşmesin, dosya insan
    tarafından okunabilsin. `indent=2`: depodaki diğer artefaktlarla aynı biçim.
    Dosya tek satır sonuyla biter; satırla bitmeyen dosya diff araçlarında gürültü
    üretir. `sort_keys` KULLANILMIYOR: anahtar sırası kodda sabit ve anlamlıdır
    (önce uyarı, sonra seçim, en sonda örnekler), sözlükler zaten ekleme sırasını
    korur ve sıralamak determinizme bir şey katmadan okuma sırasını bozardı.
    """
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _require_text(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PacketError(f"{description} boş olamaz.")
    return value.strip()


def load_cases(path: Path) -> dict[str, Any]:
    """Vaka taslağını oku ve yapısını fail-closed doğrula.

    Boş bir `cases` listesi burada hata DEĞİLDİR: dosya geçerli ama havuz boştur ve
    bunu seçim aşaması anlamlı bir mesajla söyler. Ayrımı korumak önemli, çünkü
    "dosya bozuk" ile "henüz vaka yazılmamış" farklı işler gerektirir.
    """
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise PacketError(f"Vaka dosyası okunamadı: {path}: {exc}") from exc
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PacketError(f"Vaka dosyası geçerli UTF-8 JSON değil: {path}") from exc
    if not isinstance(payload, dict):
        raise PacketError("Vaka dosyası bir JSON nesnesi olmalı.")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise PacketError("Vaka dosyası bir `cases` listesi taşımalı.")
    payload["cases"] = cases
    payload["__sha256__"] = _sha256_bytes(content)
    return payload


def check_blank_labels(case: dict[str, Any]) -> None:
    """Vakadaki insan alanlarının boş olduğunu doğrula; dolusunu REDDET.

    Sessiz düzeltme yok. Dolu bir alan iki şeyden biridir: ya biri gerçekten karar
    vermiştir (o zaman onu silmek kanıt kaybıdır), ya da beklenen puan taslağa
    kaçmıştır (o zaman etiketleyiciye cevabı göstermek olurdu). İkisinde de doğru
    davranış durup söylemektir.
    """
    case_id = case.get("id", "(kimliksiz vaka)")
    for field in BLANK_CASE_FIELDS:
        if field not in case:
            raise PacketError(f"{case_id}: etiketleyiciye sorulan `{field}` alanı yok.")
        if case[field] is not None:
            raise PacketError(
                f"{case_id}: `{field}` alanı dolu ({case[field]!r}). Etiket alanları boş "
                "olmalı; paket sessizce boşaltılmaz."
            )
    if case.get("result") != REQUIRED_RESULT:
        raise PacketError(
            f"{case_id}: `result` alanı {case.get('result')!r}; koşulmamış bir vaka "
            f"yalnız {REQUIRED_RESULT!r} olabilir."
        )
    for index, answer in enumerate(case.get("student_answers") or [], start=1):
        if not isinstance(answer, dict):
            raise PacketError(f"{case_id}: {index}. öğrenci cevabı nesne değil.")
        for field in BLANK_ANSWER_FIELDS:
            if field not in answer:
                raise PacketError(
                    f"{case_id}: {index}. cevapta etiketleyiciye sorulan `{field}` alanı yok."
                )
            if answer[field] is not None:
                raise PacketError(
                    f"{case_id}: {index}. cevabın `{field}` alanı dolu ({answer[field]!r}). "
                    "Etiket alanları boş olmalı; paket sessizce boşaltılmaz."
                )


def _rubric_payload(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Rubriği yapısal olarak doğrula.

    `app.schemas.assessment.RubricItem` ile doğrulamak `prepare_packet.py`'nin işi;
    orada zaten yapılıyor. Burada aynı şema tekrar çağrılsaydı bu modül `app`
    paketine ve pydantic'e bağlanırdı; oysa paketin bütün değeri, hiçbir uygulama
    bağımlılığı olmadan her yerde yeniden üretilebilmesinde.
    """
    case_id = case.get("id", "(kimliksiz vaka)")
    rubric = case.get("rubric")
    if rubric is None:
        rubric = []
    if not isinstance(rubric, list):
        raise PacketError(f"{case_id}: `rubric` bir liste olmalı.")
    items: list[dict[str, Any]] = []
    for index, item in enumerate(rubric, start=1):
        if not isinstance(item, dict):
            raise PacketError(f"{case_id}: {index}. rubrik maddesi nesne değil.")
        point = _require_text(item.get("point"), f"{case_id}: {index}. rubrik maddesinin metni")
        weight = item.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise PacketError(f"{case_id}: {index}. rubrik maddesinin ağırlığı tamsayı olmalı.")
        items.append({"point": point, "weight": weight})
    return items


def _source_payload(case: dict[str, Any], material_dir: Path) -> list[dict[str, Any]]:
    """Gösterilen kaynakları doğrula ve içerik özetine bağla.

    Kaynak yalnız adıyla yazılsaydı paket, materyal değiştiğinde bunu göremezdi;
    etiketleyici başka bir metne bakıp aynı pakete etiket vermiş olurdu. SHA-256
    bu sessiz kaymayı imkânsız kılar. `SourceSpec` ile doğrulama ise alan adlarını
    `prepare_packet.py` ile aynı tipe bağlar: iki artefakt aynı kaynağı iki farklı
    biçimde yazmaz.
    """
    case_id = case.get("id", "(kimliksiz vaka)")
    raw = case.get("source")
    if not isinstance(raw, dict):
        raise PacketError(f"{case_id}: `source` alanı yok ya da nesne değil.")
    try:
        spec = SourceSpec(**raw)
    except TypeError as exc:
        raise PacketError(f"{case_id}: `source` alanı SourceSpec ile uyumsuz: {exc}") from exc
    file_name = _require_text(spec.file_name, f"{case_id}: kaynak dosya adı")
    material = material_dir / file_name
    if not material.is_file():
        raise PacketError(
            f"{case_id}: gösterilen kaynak materyalde bulunamadı: {material}. "
            "Okunamayan bir kaynağa bakılarak etiket verilemez."
        )
    payload = asdict(spec)
    payload["label"] = spec.label()
    payload["sha256"] = _sha256_file(material)
    return [payload]


def build_examples(cases: list[Any], *, material_dir: Path) -> list[dict[str, Any]]:
    """Vakaları (vaka, öğrenci cevabı) çiftlerine düzleştir.

    Etiketlenen birim vaka değil, tek bir öğrenci cevabıdır: aynı soruya verilen
    doğru ve yanlış cevap ayrı ayrı yargılanır. E3'ün "≥25 örnek" ölçütü de bu
    birimle sayılır; vaka sayısıyla sayılsaydı beş vakalık bir taslak, on üç ayrı
    yargı taşıdığı hâlde "5" görünürdü.
    """
    examples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise PacketError(f"{position}. vaka bir nesne değil.")
        case_id = _require_text(case.get("id"), f"{position}. vakanın `id` alanı")
        check_blank_labels(case)
        prompt = _require_text(case.get("prompt"), f"{case_id}: soru metni")
        question_type = _require_text(case.get("question_type"), f"{case_id}: `question_type`")
        answer_format = case.get("answer_format")
        if answer_format is not None and not isinstance(answer_format, str):
            raise PacketError(f"{case_id}: `answer_format` metin ya da null olmalı.")
        sources = _source_payload(case, material_dir)
        rubric = _rubric_payload(case)
        answers = case.get("student_answers")
        if not isinstance(answers, list) or not answers:
            raise PacketError(f"{case_id}: en az bir öğrenci cevabı olmalı.")
        for index, answer in enumerate(answers, start=1):
            anchor = answer.get("anchor")
            if anchor not in ANCHOR_LABELS:
                raise PacketError(
                    f"{case_id}: {index}. cevabın çıpası {anchor!r}; "
                    f"izinli çıpalar: {', '.join(ANCHOR_LABELS)}."
                )
            text = _require_text(answer.get("answer"), f"{case_id}: {index}. öğrenci cevabı")
            # Kimlik, çıpadan ya da sıradan DEĞİL cevabın içeriğinden türer.
            # `GRADE-ESSAY-01-correct` gibi bir kimlik cevap anahtarını formun
            # başlığına yazardı; sıra numarası da taslaktaki doğru/kısmen/yanlış
            # düzenini ele verirdi. İçerik özeti ikisini de yapmaz, buna karşılık
            # aynı cevap için her koşuda aynı kalır ve cevap metni değişirse
            # değişir — değişen bir cevap zaten başka bir örnektir.
            example_id = f"{case_id}-{_sha256_bytes(text.encode('utf-8'))[:8]}"
            if example_id in seen:
                raise PacketError(
                    f"{example_id} iki kez üretildi; aynı vakada aynı çıpadan iki cevap var."
                )
            if not score_labels.ITEM_RE.match(f"## 1. {example_id} ({question_type})"):
                raise PacketError(
                    f"{example_id}: etiket formu biçimine uymayan kimlik. Vaka kimliği "
                    "yalnız harf, rakam, `-` ve `_` içerebilir."
                )
            seen.add(example_id)
            examples.append(
                {
                    "example_id": example_id,
                    "case_id": case_id,
                    "question_type": question_type,
                    "answer_format": answer_format,
                    "question": prompt,
                    "answer": text,
                    "anchor": anchor,
                    "sources": sources,
                    "rubric": rubric,
                    "labeler_fields": {"label": None, "note": None},
                }
            )
    return examples


def select_examples(
    examples: list[dict[str, Any]], *, size: int, seed: int
) -> list[dict[str, Any]]:
    """Sabit tohumla deterministik seçim.

    Rastgelelik şart: "ilginç görünen" örnekleri seçmek örneklemi bozar ve
    "beğendiğiniz örnekleri seçtiniz" itirazına verecek cevap kalmaz. Tohum sabit
    olduğu için seçim yine de tekrar üretilebilir. Aynı idiom `pull_sample.py`de de
    kullanılıyor; iki örneklem aynı biçimde seçilsin diye bilinçli olarak aynı.
    """
    if size <= 0:
        raise PacketError("Örnek sayısı pozitif olmalı.")
    if not examples:
        raise PacketError(
            "Vaka dosyasında hiç örnek yok; boş bir havuzdan kabul paketi üretilemez."
        )
    if size > len(examples):
        raise PacketError(
            f"{size} örnek istendi ama havuzda yalnız {len(examples)} var. "
            f"E3 en az {E3_MINIMUM_EXAMPLES} GERÇEK örnek istiyor; eksik örnek "
            "uydurulmaz, paket üretilmez."
        )
    pool = list(examples)
    # S311: kriptografik değil — tam tersine, seçimin YENİDEN ÜRETİLEBİLİR olması için
    # sabit tohumlu üreteç şart. Tahmin edilemez olsaydı paket doğrulanamazdı.
    random.Random(seed).shuffle(pool)  # noqa: S311
    return pool[:size]


def check_packet_integrity(packet: dict[str, Any]) -> None:
    """Paketin bütünlüğünü doğrula: alanlar var mı, etiket alanları BOŞ mu.

    Bu kontrol üretimde de, `--verify` sırasında da koşar. İkincisi önemli: diskteki
    bir pakete elle etiket yazılmışsa, o paket artık "etiketleyiciye verilecek boş
    form" değildir ve bayt karşılaştırmasından önce reddedilmelidir.
    """
    if packet.get("kind") != PACKET_KIND:
        raise PacketError(f"kind={PACKET_KIND} olmayan dosya kabul paketi değil.")
    examples = packet.get("examples")
    if not isinstance(examples, list) or not examples:
        raise PacketError("Pakette hiç örnek yok.")
    seen: set[str] = set()
    for position, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            raise PacketError(f"{position}. örnek bir nesne değil.")
        example_id = example.get("example_id")
        if not isinstance(example_id, str) or not example_id:
            raise PacketError(f"{position}. örneğin `example_id` alanı yok.")
        if example_id in seen:
            raise PacketError(f"Pakette yinelenen örnek kimliği: {example_id}")
        seen.add(example_id)
        for field in ("question", "answer"):
            if not isinstance(example.get(field), str) or not example[field].strip():
                raise PacketError(f"{example_id}: `{field}` alanı boş.")
        sources = example.get("sources")
        if not isinstance(sources, list) or not sources:
            raise PacketError(f"{example_id}: gösterilen kaynak yok.")
        for source in sources:
            if not isinstance(source, dict):
                raise PacketError(f"{example_id}: kaynak kaydı nesne değil.")
            for field in ("file_name", "sha256"):
                if not isinstance(source.get(field), str) or not source[field]:
                    raise PacketError(f"{example_id}: kaynağın `{field}` alanı yok.")
        fields = example.get("labeler_fields")
        if not isinstance(fields, dict):
            raise PacketError(f"{example_id}: etiketleyiciye sorulan alanlar yok.")
        for field in ("label", "note"):
            if field not in fields:
                raise PacketError(f"{example_id}: etiketleyici alanı `{field}` yok.")
            if fields[field] is not None:
                raise PacketError(
                    f"{example_id}: etiketleyici alanı `{field}` dolu ({fields[field]!r}). "
                    "Paket boş formla verilir; dolu bir alan sessizce temizlenmez."
                )
        if "anchor" in example:
            raise PacketError(
                f"{example_id}: `anchor` alanı pakette görünüyor. Çıpa cevap anahtarıdır "
                "ve etiketleyiciye verilen dosyaya giremez."
            )


def build_packet(
    *,
    cases_path: Path = DEFAULT_CASES,
    material_dir: Path = DEFAULT_MATERIAL_DIR,
    size: int = DEFAULT_SIZE,
    seed: int = DEFAULT_SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Paketi ve (ayrı tutulan) cevap anahtarını üret.

    İkisi ayrı dönüyor çünkü ayrı dosyalara yazılıyorlar ve ayrı kişilere gidiyorlar:
    paket etiketleyiciye, anahtar yalnız skorlamayı yapana. Tek bir sözlük dönseydi
    çağıranın çıpayı elemeyi unutması an meselesi olurdu.
    """
    draft = load_cases(cases_path)
    examples = build_examples(draft["cases"], material_dir=material_dir)
    chosen = select_examples(examples, size=size, seed=seed)

    materials: dict[str, str] = {}
    for example in chosen:
        for source in example["sources"]:
            materials[source["file_name"]] = source["sha256"]

    public_examples = [
        {key: value for key, value in example.items() if key != "anchor"} for example in chosen
    ]
    packet = {
        "schema_version": 1,
        "kind": PACKET_KIND,
        "warning": PACKET_WARNING,
        "selection": {
            "seed": seed,
            "size": len(chosen),
            "pool_size": len(examples),
            "method": "random.Random(seed).shuffle(pool)[:size]",
            "unit": "case_x_student_answer",
        },
        "acceptance": {
            "minimum_examples": E3_MINIMUM_EXAMPLES,
            "meets_minimum": len(chosen) >= E3_MINIMUM_EXAMPLES,
            "real_provider_quality": "pending",
            "independent_human_review": "pending",
            "grading_run": "not_run",
        },
        "inputs": {
            "cases_file": cases_path.name,
            "cases_sha256": draft["__sha256__"],
            "materials": [
                {"file_name": name, "sha256": materials[name]} for name in sorted(materials)
            ],
        },
        "label_scale": {
            "values": list(LABEL_VALUES),
            "ordinal_scores": dict(LABEL_SCORES),
            "note": "Üç değerli ve sıralı ölçek; ara değer üretilmez.",
        },
        "examples": public_examples,
    }
    check_packet_integrity(packet)
    answer_key = {
        "schema_version": 1,
        "kind": ANSWER_KEY_KIND,
        "warning": (
            "Cevap anahtarıdır. Etiketleyiciye VERİLMEZ; yalnız etiketler toplandıktan "
            "sonra çıpa uyumunu hesaplamak için kullanılır."
        ),
        "anchor_labels": dict(ANCHOR_LABELS),
        "anchors": {example["example_id"]: example["anchor"] for example in chosen},
    }
    return packet, answer_key


def render_label_file(packet: dict[str, Any], labeller: str) -> str:
    """Etiketleyici başına AYRI form: biri diğerinin kararını görmemeli.

    Biçim `pull_sample.write_label_file` ile aynı iskelettedir ve ayrıştırma
    `score_labels` içindeki AYNI düzenli ifadelerle yapılır. Biçim kopyalansaydı
    iki dosya zamanla birbirinden kayar ve bir gün form üretilebilir ama
    okunamaz hâle gelirdi.

    Çıpa bu dosyaya YAZILMAZ; beklenen puan da yazılmaz. Etiketleyicinin elinde
    yalnız soru, öğrenci cevabı, gösterilen kaynak ve rubrik vardır.
    """
    selection = packet["selection"]
    acceptance = packet["acceptance"]
    scale = " / ".join(f"`{value}`" for value in LABEL_VALUES)
    lines = [
        f"# Kabul paketi etiketleme — {labeller}. etiketleyici",
        "",
        f"Paket: `{PACKET_FILE}` · n={selection['size']} · tohum {selection['seed']}",
        "",
        "**Bu dosyayı doldururken diğer etiketleyicinin dosyasına BAKMAYIN.** Ham uyum",
        "oranı, tartışma öncesi etiketlerden hesaplanır; sonrasından hesaplanan uyum",
        "her zaman %100 çıkar ve hiçbir şey ölçmez.",
        "",
        f"Etiket üç değerlidir, ara değer üretilmez: {scale}. Etiket, cevabın",
        "ikna ediciliğine değil **gösterilen kaynağın ve rubriğin içeriğine** bakılarak",
        "verilir.",
        "",
        "> **UYARI — BU BİR KABUL SONUCU DEĞİLDİR.** Paket çevrimdışı üretildi; gerçek",
        "> sağlayıcı koşusu yapılmadı ve model cevabı içermiyor. Bu form insan çıpalarını",
        "> sabitler; model kalitesi hakkında hiçbir şey söylemez.",
        "",
    ]
    if not acceptance["meets_minimum"]:
        lines += [
            f"> **UYARI — ÖRNEK SAYISI YETERSİZ.** Pakette {selection['size']} örnek var;",
            f"> E3 en az {E3_MINIMUM_EXAMPLES} örnek istiyor. Bu form süreci sınar,",
            "> kabul ölçütünü karşılamaz.",
            "",
        ]
    lines += ["---", ""]

    for index, example in enumerate(packet["examples"], start=1):
        lines += [
            f"## {index}. {example['example_id']} ({example['question_type']})",
            "",
            f"**Soru:** {example['question']}",
            "",
            "**Öğrenci cevabı:**",
            "",
            "> " + example["answer"].replace("\n", "\n> "),
            "",
            "**Gösterilen kaynaklar:**",
            "",
        ]
        for source in example["sources"]:
            # `SourceSpec.label()` daraltma alanı yoksa dosya adının kendisidir;
            # aynı adı iki kez yazmak formu okunmaz yapar, o yüzden tekrar edilmez.
            label = source.get("label") or source["file_name"]
            suffix = "" if label == source["file_name"] else f" — {label}"
            lines.append(f"- `{source['file_name']}`{suffix}")
            lines.append(f"  > sha256 `{source['sha256']}`")
        lines += ["", "**Rubrik:**", ""]
        if example["rubric"]:
            for item in example["rubric"]:
                lines.append(f"- {item['point']} (ağırlık {item['weight']})")
        else:
            lines.append("- (rubrik yazılmadı; bu vakada puanlama ölçütü henüz yok)")
        lines += [
            "",
            f"**Etiket:** {scale} → ______________",
            "",
            "**Not:** ______________",
            "",
        ]
    return "\n".join(lines)


def packet_files(
    *,
    cases_path: Path = DEFAULT_CASES,
    material_dir: Path = DEFAULT_MATERIAL_DIR,
    size: int = DEFAULT_SIZE,
    seed: int = DEFAULT_SEED,
) -> dict[str, bytes]:
    """Paketin BÜTÜN dosyalarını bellekte üretir; diske yazmaz.

    Üretim ile yazmanın ayrılması `--verify`nin tek nedenidir: doğrulama, diske
    hiçbir şey yazmadan aynı baytları üretip karşılaştırabilmelidir. Aynı fonksiyon
    hem yazma hem doğrulama yolunda koştuğu için iki yolun ayrışması mümkün değil.
    """
    packet, answer_key = build_packet(
        cases_path=cases_path, material_dir=material_dir, size=size, seed=seed
    )
    files: dict[str, bytes] = {
        PACKET_FILE: canonical_json(packet),
        ANSWER_KEY_FILE: canonical_json(answer_key),
    }
    for index, name in enumerate(LABEL_FILES, start=1):
        files[name] = (render_label_file(packet, str(index)) + "\n").encode("utf-8")
    checksums = "\n".join(f"{_sha256_bytes(files[name])}  {name}" for name in sorted(files))
    files[CHECKSUM_FILE] = (checksums + "\n").encode("utf-8")
    return files


def packet_digest(files: dict[str, bytes]) -> str:
    """Paketin tek satırlık özeti: `packet.json` dosyasının SHA-256'sı.

    Depo kanıtı hash ile bağlıyor (`prepare_packet.py` kaynakları, `score_labels.py`
    örneklem ve etiket dosyalarını özetliyor). Aynı duruş burada da: bir rapora
    "şu paketle ölçüldü" yazılacaksa yazılacak şey bu dizedir.
    """
    return _sha256_bytes(files[PACKET_FILE])


def write_packet(files: dict[str, bytes], output_dir: Path) -> None:
    """Paketi yeni bir dizine yazar; var olan dizinin üzerine YAZMAZ.

    `prepare_packet.py` ile aynı kural (`exist_ok=False`): var olan bir paket
    dizininde doldurulmuş etiket dosyaları olabilir ve onları boş formla ezmek,
    insanın yaptığı işi silmek olurdu.
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise PacketError(
            f"Çıktı dizini zaten var: {output_dir}. Doldurulmuş etiket dosyalarının "
            "üzerine yazılmaz; yeni bir dizin verin."
        ) from exc
    except OSError as exc:
        raise PacketError(f"Çıktı dizini oluşturulamadı: {output_dir}: {exc}") from exc
    for name, content in files.items():
        (output_dir / name).write_bytes(content)


def verify_packet(output_dir: Path, files: dict[str, bytes]) -> dict[str, Any]:
    """Diskteki paketi yeniden üretilenle BAYT olarak karşılaştırır.

    Fark üç biçimde görünür: dosya eksik, içerik farklı, ya da pakette olmayan fazla
    bir dosya var. Üçü de raporlanır; yalnız "farklı" denseydi, birinin elle eklediği
    bir dosya görünmez kalırdı.
    """
    differences: list[dict[str, str]] = []
    for name, expected in files.items():
        path = output_dir / name
        if not path.is_file():
            differences.append({"file": name, "kind": "missing", "detail": "dosya yok"})
            continue
        actual = path.read_bytes()
        if actual != expected:
            differences.append(
                {
                    "file": name,
                    "kind": "content",
                    "detail": (
                        f"beklenen sha256 {_sha256_bytes(expected)}, "
                        f"diskteki {_sha256_bytes(actual)}"
                    ),
                }
            )
    if output_dir.is_dir():
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.name not in files:
                differences.append(
                    {"file": path.name, "kind": "extra", "detail": "pakette olmayan dosya"}
                )
    return {
        "kind": "acceptance_packet_verification",
        "directory": str(output_dir),
        "expected_packet_sha256": packet_digest(files),
        "identical": not differences,
        "differences": differences,
    }


def load_labels(path: Path) -> list[tuple[str, str, str]]:
    """Etiket dosyasını `score_labels` ile AYNI düzenli ifadelerle ayrıştır.

    Sözcük dağarcığı farklı: faithfulness ölçeği `destekleniyor/kısmen/desteklenmiyor`,
    kabul paketinin ölçeği `doğru/kısmen/yanlış`. Bu yüzden `score_labels.load_labels`
    doğrudan çağrılamaz; ama BİÇİM aynı kalmalı, o yüzden düzenli ifadeler oradan
    alınır, kopyalanmaz. Böylece biçim bir gün değişirse iki araç birlikte değişir.

    Doldurulmamış satır sessizce atlanmaz: eksik etiket, uyum hesabını gizlice
    küçültür ve n'i bozar.
    """
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise PacketError(f"Etiket dosyası okunamadı: {path}: {exc}") from exc
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PacketError(f"Etiket dosyası UTF-8 değil: {path}") from exc

    current: str | None = None
    ordered: list[str] = []
    labels: dict[str, str] = {}
    notes: dict[str, str] = {}
    for line in lines:
        item_match = score_labels.ITEM_RE.match(line)
        if item_match:
            current = item_match.group(1)
            if current in ordered:
                raise PacketError(f"Etiket dosyasında yinelenen örnek kimliği: {current}")
            ordered.append(current)
            continue
        label_match = score_labels.LABEL_RE.match(line)
        if label_match:
            if current is None:
                raise PacketError("Bir etiket, örnek başlığından önce yazılmış.")
            if current in labels:
                raise PacketError(f"{current} için birden fazla etiket satırı var.")
            labels[current] = _normalise_label(label_match.group(1), current)
            continue
        note_match = score_labels.NOTE_RE.match(line)
        if note_match and current is not None:
            note = note_match.group(1).strip()
            notes[current] = "" if not note or set(note) <= {"_"} else note

    if not ordered:
        raise PacketError(f"Etiket dosyasında hiçbir örnek bulunamadı: {path}")
    missing = [item for item in ordered if item not in labels]
    if missing:
        raise PacketError(f"Etiket satırı olmayan örnek(ler): {', '.join(missing)}")
    return [(item, labels[item], notes.get(item, "")) for item in ordered]


def _normalise_label(raw: str, example_id: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    # Formdaki ölçek satırı (`doğru` / `kısmen` / `yanlış` → ____) doldurulmadan
    # kalmışsa altçizgi kalır; bunu "etiket verilmiş" saymak uydurma olurdu.
    if not value or set(value) <= {"_"} or value == "[ETİKETLENMEDİ]":
        raise PacketError(f"{example_id} henüz etiketlenmemiş.")
    if value not in LABEL_VALUES:
        raise PacketError(
            f"{example_id} için geçersiz etiket {value!r}; izinli: {', '.join(LABEL_VALUES)}."
        )
    return value


def ordinal_agreement(first: list[str], second: list[str]) -> dict[str, Any]:
    """Sıralı etiketler için uyum; `rater_agreement` varsa ondan, yoksa nominalden.

    Neden sıralı: `doğru` > `kısmen` > `yanlış` bir ölçektir. Etiketleyicilerden biri
    `doğru`, öteki `yanlış` dediyse çıpayı taban tabana zıt okumuşlardır; biri `doğru`
    öteki `kısmen` dediyse sınırda ayrılmışlardır. Nominal kappa ikisini de tek bir
    "anlaşamadılar" kutusuna atar. `evaluation/rater_agreement.py` kuadratik ağırlıklı
    kappa'yı (QWK) zaten hesaplıyor; kopyalamak yerine oradan çağrılır.

    Dosya bulunamazsa hesap `metrics.label_agreement` ile nominal olarak sürer ve
    rapor hangi arka ucun kullanıldığını `backend` alanında YAZAR. Sessizce daha
    zayıf bir sayıya düşmek, raporu okuyanın fark edemeyeceği bir gerilemedir.
    """
    scores_first = [LABEL_SCORES[label] for label in first]
    scores_second = [LABEL_SCORES[label] for label in second]
    categories = tuple(sorted(set(LABEL_SCORES.values())))
    try:
        import rater_agreement
    except ImportError:
        return {
            "backend": "metrics.label_agreement",
            "backend_note": (
                "rater_agreement.py bulunamadı; yalnız nominal kappa hesaplandı. "
                "Sıralı ölçekte nominal kappa yakın ve uzak anlaşmazlığı ayırt etmez."
            ),
            "ordinal_scores": dict(LABEL_SCORES),
            **metrics.label_agreement(first, second).as_dict(),
        }
    report = rater_agreement.agreement_report(scores_first, scores_second, categories=categories)
    return {
        "backend": "rater_agreement.agreement_report",
        "backend_note": (
            "Kuadratik ağırlıklı kappa (QWK) sıralı ölçek için doğru olandır; nominal "
            "kappa karşılaştırma için yanında durur. Eşik YOKTUR: E4'te olduğu gibi "
            "eşik insan-insan uyumu ölçüldükten sonra dışarıda belirlenir."
        ),
        "ordinal_scores": dict(LABEL_SCORES),
        **report.as_dict(),
    }


def reconcile(
    packet: dict[str, Any],
    answer_key: dict[str, Any] | None,
    first_path: Path,
    second_path: Path,
    *,
    first_name: str,
    second_name: str,
    attested: bool,
) -> dict[str, Any]:
    """İki bağımsız etiket dosyasını pakete bağla ve uyumu hesapla.

    Araç etiket ÜRETMEZ ve insan yerine karar vermez. Yaptığı iş, tartışma öncesi
    etiketleri dondurup uyuşmazlıkları ayrı bir listeye çıkarmaktır; nihai kararlar
    sonradan verilir ve ham uyumun üzerine yazılmaz.

    `score_labels.py` ile aynı fail-closed kapılar: bağımsızlık beyanı, iki farklı
    kişi adı, örnek kimlik ve SIRASININ birebir eşleşmesi. Sıra da eşleşmeli, çünkü
    iki dosya farklı sırada doldurulmuşsa etiketler yanlış örneklerle eşleşir ve
    ortaya çıkan sayı uyum değil gürültüdür.
    """
    if not attested:
        raise PacketError(
            "Rapor için iki dosyanın bağımsız doldurulduğu --attest-independent ile onaylanmalı."
        )
    first_name = first_name.strip()
    second_name = second_name.strip()
    if not first_name or not second_name:
        raise PacketError("İki etiketleyicinin adı da boş olamaz.")
    if first_name.casefold() == second_name.casefold():
        raise PacketError("İki bağımsız etiketleyici aynı kişi olamaz.")

    check_packet_integrity(packet)
    expected_ids = [example["example_id"] for example in packet["examples"]]
    first_entries = load_labels(first_path)
    second_entries = load_labels(second_path)
    for path, entries in ((first_path, first_entries), (second_path, second_entries)):
        if [item for item, _, _ in entries] != expected_ids:
            raise PacketError(f"{path.name} örnek kimlikleri/sırası paketle birebir eşleşmiyor.")

    first_labels = [label for _, label, _ in first_entries]
    second_labels = [label for _, label, _ in second_entries]
    agreement = metrics.label_agreement(first_labels, second_labels)

    anchors = (answer_key or {}).get("anchors") or {}
    anchor_concordance: dict[str, Any] | None = None
    if anchors:
        expected_labels = [ANCHOR_LABELS.get(anchors.get(item, "")) for item in expected_ids]
        anchor_concordance = {
            "note": (
                "İnsan etiketinin taslaktaki çıpayla aynı olup olmadığı. Çıpa doğruluk "
                "ölçütü DEĞİLDİR; henüz hoca onayı almamış bir taslaktır."
            ),
            "labeler_1_matches": sum(
                1
                for expected, actual in zip(expected_labels, first_labels, strict=True)
                if expected == actual
            ),
            "labeler_2_matches": sum(
                1
                for expected, actual in zip(expected_labels, second_labels, strict=True)
                if expected == actual
            ),
            "n": len(expected_ids),
        }

    disagreements = [
        {
            "example_id": item,
            "question": example["question"],
            "labeler_1_label": first_label,
            "labeler_1_note": first_note,
            "labeler_2_label": second_label,
            "labeler_2_note": second_note,
            "resolution_status": "pending",
            "final_label": None,
        }
        for example, (item, first_label, first_note), (_, second_label, second_note) in zip(
            packet["examples"], first_entries, second_entries, strict=True
        )
        if first_label != second_label
    ]
    return {
        "schema_version": 1,
        "kind": REPORT_KIND,
        "reportable": False,
        "warning": (
            "Bu rapor uyum HESABINI sabitler; E3'ü tamamlamaz. Gerçek sağlayıcı koşusu "
            "ve iki bağımsız insan etiketleyici hâlâ ENGEL."
        ),
        "blockers": [
            "gerçek sağlayıcı koşusu yapılmadı",
            "iki bağımsız insan etiketleyici oturumu yapılmadı",
        ],
        "packet_sha256": _sha256_bytes(canonical_json(packet)),
        "methodology": {
            "independent_labeling_attested": True,
            "agreement_basis": "pre_adjudication_labels",
            "allowed_labels": list(LABEL_VALUES),
        },
        "labelers": [
            {
                "name": first_name,
                "file": first_path.name,
                "sha256": _sha256_file(first_path),
                "distribution": {value: first_labels.count(value) for value in LABEL_VALUES},
            },
            {
                "name": second_name,
                "file": second_path.name,
                "sha256": _sha256_file(second_path),
                "distribution": {value: second_labels.count(value) for value in LABEL_VALUES},
            },
        ],
        "agreement": agreement.as_dict(),
        "ordinal_agreement": ordinal_agreement(first_labels, second_labels),
        "anchor_concordance": anchor_concordance,
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except OSError as exc:
        raise PacketError(f"{description} okunamadı: {path}: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PacketError(f"{description} geçerli UTF-8 JSON değil: {path}") from exc
    if not isinstance(payload, dict):
        raise PacketError(f"{description} bir JSON nesnesi olmalı.")
    return payload


def _run_build(args: argparse.Namespace) -> int:
    files = packet_files(
        cases_path=args.cases, material_dir=args.material_dir, size=args.size, seed=args.seed
    )
    write_packet(files, args.output_dir)
    print(f"Kabul paketi: {args.output_dir} · örnek={args.size} · tohum={args.seed}")
    print(f"{PACKET_FILE} sha256: {packet_digest(files)}")
    if args.size < E3_MINIMUM_EXAMPLES:
        print(f"UYARI: {args.size} örnek, E3'ün istediği {E3_MINIMUM_EXAMPLES} örneğin altında.")
    print("E3 AÇIK: gerçek sağlayıcı koşusu ve iki bağımsız insan etiketleyici hâlâ eksik.")
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    on_disk = _load_json(args.output_dir / PACKET_FILE, "Paket")
    check_packet_integrity(on_disk)
    files = packet_files(
        cases_path=args.cases, material_dir=args.material_dir, size=args.size, seed=args.seed
    )
    result = verify_packet(args.output_dir, files)
    if result["identical"]:
        print(f"Paket yeniden üretildi ve BİREBİR aynı: {args.output_dir}")
        print(f"{PACKET_FILE} sha256: {result['expected_packet_sha256']}")
        return 0
    print(f"FARK VAR: {args.output_dir}", file=sys.stderr)
    for difference in result["differences"]:
        print(f"- {difference['file']}: {difference['kind']} — {difference['detail']}")
    return 3


def _run_reconcile(args: argparse.Namespace) -> int:
    if args.first is None or args.second is None:
        raise PacketError("Uzlaştırma için hem --first hem --second verilmeli.")
    if args.report_out is None:
        raise PacketError("Uzlaştırma raporu için --report-out verilmeli.")
    if args.report_out.exists() or args.report_out.is_symlink():
        raise PacketError(
            f"Var olan raporun üzerine yazılmaz: {args.report_out}. Yeni bir yol verin."
        )
    packet = _load_json(args.output_dir / PACKET_FILE, "Paket")
    key_path = args.output_dir / ANSWER_KEY_FILE
    answer_key = _load_json(key_path, "Cevap anahtarı") if key_path.is_file() else None
    report = reconcile(
        packet,
        answer_key,
        args.first,
        args.second,
        first_name=args.labeler_1 or "",
        second_name=args.labeler_2 or "",
        attested=args.attest_independent,
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    with args.report_out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    agreement = report["agreement"]
    print(
        f"n={agreement['n']} · ham uyum={agreement['raw_agreement']:.4f} "
        f"· uyuşmazlık={report['disagreement_count']}"
    )
    print(f"Rapor: {args.report_out}")
    print("E3 AÇIK: bu rapor uyum hesabını sabitler, kabulü tamamlamaz.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E3 kabul paketinin çevrimdışı üretimi, doğrulaması ve uyum hesabı."
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Paket dizini.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--material-dir", type=Path, default=DEFAULT_MATERIAL_DIR)
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Var olan paketi yeniden üretip bayt bayt karşılaştırır.",
    )
    parser.add_argument("--first", type=Path, help="1. etiketleyicinin doldurduğu dosya.")
    parser.add_argument("--second", type=Path, help="2. etiketleyicinin doldurduğu dosya.")
    parser.add_argument("--labeler-1")
    parser.add_argument("--labeler-2")
    parser.add_argument(
        "--attest-independent",
        action="store_true",
        help="İki dosyanın tartışma öncesi, birbirini görmeden doldurulduğunu onaylar.",
    )
    parser.add_argument("--report-out", type=Path, help="Uzlaştırma raporunun yazılacağı yol.")
    args = parser.parse_args(argv)

    try:
        if args.first is not None or args.second is not None:
            return _run_reconcile(args)
        if args.verify:
            return _run_verify(args)
        return _run_build(args)
    except PacketError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
