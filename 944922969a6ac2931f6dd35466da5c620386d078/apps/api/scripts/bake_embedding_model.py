"""Embedding modelini imaja gömer, int8'e indirir ve vektör uzayını DOĞRULAR (T048).

Docker build'inde koşar (`apps/api/Dockerfile`, builder aşaması). Çalışma zamanında
HuggingFace'e hiç gidilmemesinin yolu modelin build'de indirilip imajda kalmasıdır;
demo günü ağ yavaşsa ilk soru dakikalarca sürer, ağ yoksa sistem hiç cevap veremez.

## Neden int8

`intfloat/multilingual-e5-large` fp32 ONNX ağırlıkları ~2.1 GB. Dinamik int8
quantizasyonu bunu yaklaşık üçte birine indirir; hem imaj hem replika belleği küçülür
(ACA hedefi ≤ 2 vCPU / 4 GiB).

## Neden doğrulama zorunlu

Quantizasyon ağırlıkları KAYIPLI biçimde yeniden yazar. Üretilen vektörler fp32'nin
uzayından anlamlı biçimde saparsa, indekste duran fp32 vektörleriyle int8 sorgu
vektörünü karşılaştırmak sessizce yanlış sonuç verir — hata mesajı yoktur, yalnız
retrieval kalitesi düşer. Bu yüzden betik aynı metinler için iki embedding üretip
kosinüs benzerliğini ölçer ve eşiğin altındaysa **build'i düşürür**. Denklik
kanıtlanamıyorsa doğru karar korpusu int8 ile yeniden işlemektir ve bu bir ingest
zamanı kararıdır (`config.py`: "EMBEDDING_PROVIDER çalışma zamanı yedeği değildir").

## Kullanım

    python scripts/bake_embedding_model.py --cache-dir /opt/models
    python scripts/bake_embedding_model.py --cache-dir /tmp/x --min-cosine 0.99

`--cache-dir` DIŞINDA hiçbir şeye dokunulmaz.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

#: Denklik eşiği. 0.99 keyfi değil: 1024 boyutlu normalize vektörlerde 0.99 kosinüs,
#: sıralamayı bozmayacak kadar küçük bir açı farkı demektir. Altına düşerse quantize
#: edilmiş model artık aynı uzayda sayılamaz ve korpus yeniden işlenmelidir.
DEFAULT_MIN_COSINE = 0.99

#: Ölçüm metinleri ders materyalini temsil eder: Türkçe, İngilizce ve karışık teknik
#: metin. Tek dilde ölçmek yanıltıcı olurdu — model çok dilli seçilmişti.
PROBE_TEXTS = [
    "Deadlock oluşabilmesi için dört Coffman koşulunun aynı anda sağlanması gerekir.",
    "Round Robin çizelgelemede quantum süresi bağlam değiştirme maliyetini belirler.",
    "Sayfalama (paging) sanal bellekte dış parçalanmayı ortadan kaldırır.",
    "A B-tree index keeps keys sorted and supports logarithmic range queries.",
    "The producer-consumer problem is solved with a bounded buffer and semaphores.",
    "TCP üç aşamalı el sıkışma (three-way handshake) ile bağlantı kurar.",
    "Normalizasyon, 3NF'de geçişli bağımlılıkları kaldırarak güncelleme anomalilerini önler.",
    "Bir süreç (process) ile iş parçacığı (thread) arasındaki temel fark adres alanıdır.",
]


def _log(message: str) -> None:
    print(f"[bake] {message}", flush=True)


def _snapshot_dir(cache_dir: Path) -> Path:
    """fastembed'in indirdiği model anlık görüntüsünün klasörü."""
    candidates = sorted(cache_dir.glob("models--*/snapshots/*"))
    if not candidates:
        raise SystemExit(f"model anlık görüntüsü bulunamadı: {cache_dir}")
    if len(candidates) > 1:
        raise SystemExit(f"birden fazla anlık görüntü var, hangisi belirsiz: {candidates}")
    return candidates[0]


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


def _embed(cache_dir: Path, model_name: str) -> list[list[float]]:
    """Üretimin kullandığı sağlayıcıyla embedding üretir.

    Tokenizasyon, havuzlama ve `passage:` öneki dâhil TÜM yol üretimdekiyle aynı
    olsun diye `FastEmbedProvider` kullanılır; burada elle yeniden yazılsaydı ölçüm
    modeli değil bu betiğin kopyasını sınardı.
    """
    from app.modules.ingestion.embedding import FastEmbedProvider

    provider = FastEmbedProvider(model_name=model_name, cache_dir=str(cache_dir))
    return provider.embed_documents(PROBE_TEXTS)


def _download(cache_dir: Path, model_name: str) -> None:
    _log(f"fp32 model indiriliyor / doğrulanıyor: {model_name}")
    from app.modules.ingestion.embedding import FastEmbedProvider

    # Tek bir kısa metin, indirmeyi ve ONNX oturumunun gerçekten kurulduğunu tetikler.
    FastEmbedProvider(model_name=model_name, cache_dir=str(cache_dir)).embed_query("ısınma")


def _quantize(snapshot: Path) -> tuple[int, int]:
    """model.onnx'i dinamik int8'e indirir; (fp32_bayt, int8_bayt) döndürür.

    Harici ağırlık dosyası (`model.onnx_data`) quantize edilmiş modelde tek dosyaya
    gömülür, bu yüzden sonrasında silinir — kalırsa imajda 2 GB ölü ağırlık taşınır.
    """
    # onnxruntime.quantization tip bilgisi taşımıyor; `onnx` zaten yalnız build
    # aşamasında kurulu olduğu için çalışma zamanı kodu bu içe aktarmayı görmez.
    from onnxruntime.quantization import QuantType, quantize_dynamic  # type: ignore[import-untyped]

    source = snapshot / "model.onnx"
    external = snapshot / "model.onnx_data"
    target = snapshot / "model.int8.onnx"

    fp32_bytes = source.stat().st_size + (external.stat().st_size if external.exists() else 0)
    _log(f"quantizasyon başlıyor (fp32 {fp32_bytes / 1e9:.2f} GB)")

    quantize_dynamic(
        model_input=source,
        model_output=target,
        weight_type=QuantType.QInt8,
        extra_options={
            # Ağırlıklar int8'e iner, aktivasyonlar float kalır: dinamik quantizasyon
            # kalibrasyon verisi istemez, bu yüzden build aşamasında koşabilir.
            "MatMulConstBOnly": True,
            # Şekil çıkarımı KAPALI. Varsayılan yol modeli "-inferred.onnx" olarak
            # diske ikinci kez yazar; harici ağırlıklı 2.1 GB'lık bu modelde bu,
            # build sırasında ~4.5 GB tepe disk demek. 9 Ağustos'ta yerel denemede
            # ölçüldü: boş alan 5.0 GB'den 1.0 GB'ye on saniyede indi ve koşu
            # emniyet için durduruldu. Dinamik quantizasyon yalnız sabit ağırlıkları
            # yeniden yazar; çıkarılmış şekillere ihtiyacı yoktur.
            "DisableShapeInference": True,
        },
    )
    int8_bytes = target.stat().st_size
    _log(f"quantizasyon bitti (int8 {int8_bytes / 1e9:.2f} GB)")
    return fp32_bytes, int8_bytes


def _swap_in_int8(snapshot: Path, cache_dir: Path) -> None:
    """int8 modelini `model.onnx` yerine koyar ve fp32 ağırlıklarını siler.

    fastembed dosya adını sabit okur; imajda int8'in çalışması için ad değişimi şart.

    Ayrıca `files_metadata.json` güncellenir. Neden kritik: fastembed indirdiği
    dosyaların boyutunu bu dosyadaki kayıtla karşılaştırır. Swap'ten sonra kayıt
    fp32 boyutunu gösterdiği için uyuşmazlık oluşur ("Local file sizes do not match
    the metadata" — 9 Ağustos'ta ölçümde birebir gözlendi) ve ağ varken kütüphane
    modeli YENİDEN İNDİREBİLİR. Bu, imaja model gömmenin tüm amacını ortadan
    kaldırırdı; `HF_HUB_OFFLINE=1` ikinci bir emniyet kemeridir, tek dayanak değil.
    """
    source = snapshot / "model.onnx"
    external = snapshot / "model.onnx_data"
    target = snapshot / "model.int8.onnx"

    # Symlink olabilir (HF blob düzeni); unlink her iki durumda da doğru.
    source.unlink(missing_ok=True)
    if external.exists() or external.is_symlink():
        external.unlink()
    shutil.move(str(target), str(source))

    _rewrite_metadata(cache_dir, source)


def _rewrite_metadata(cache_dir: Path, model_file: Path) -> None:
    """`files_metadata.json`'u swap sonrası gerçek dosyalarla tutarlı hâle getirir."""
    for metadata_path in cache_dir.glob("models--*/files_metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        updated: dict[str, object] = {}
        for key, value in metadata.items():
            name = key.rsplit("/", 1)[-1]
            if name == "model.onnx_data":
                continue  # artık yok: ağırlıklar int8 dosyasının içinde
            if name == "model.onnx" and isinstance(value, dict):
                value = {**value, "size": model_file.stat().st_size}
            updated[key] = value
        metadata_path.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")

    # Aynı bilgiyi taşıyan `trees/<sha>.json` de varsa tutarlı kalmalı.
    for tree_path in cache_dir.glob("models--*/trees/*.json"):
        try:
            tree = json.loads(tree_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(tree, dict):
            continue
        pruned = {key: value for key, value in tree.items() if not key.endswith("model.onnx_data")}
        if pruned != tree:
            tree_path.write_text(json.dumps(pruned, ensure_ascii=False), encoding="utf-8")


def _prune_blobs(cache_dir: Path) -> None:
    """Artık hiçbir snapshot dosyasının işaret etmediği HF blob'larını siler.

    HF önbelleği snapshot'ta symlink, `blobs/` altında gerçek dosya tutar. int8 swap'i
    symlink'leri kaldırır ama 2 GB'lık blob yerinde kalır ve imaja girer.
    """
    blobs = cache_dir.glob("models--*/blobs/*")
    referenced = {
        path.resolve()
        for path in cache_dir.glob("models--*/snapshots/*/*")
        if path.is_symlink() or path.is_file()
    }
    freed = 0
    for blob in blobs:
        if blob.resolve() not in referenced:
            freed += blob.stat().st_size
            blob.unlink()
    if freed:
        _log(f"başvurulmayan blob'lar silindi: {freed / 1e9:.2f} GB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--min-cosine", type=float, default=DEFAULT_MIN_COSINE)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="model zaten cache-dir'de; yeniden indirme (yerel ölçüm için)",
    )
    parser.add_argument("--report", type=Path, help="ölçüm sonucunu JSON olarak yaz")
    parser.add_argument(
        "--no-quantize",
        action="store_true",
        help=(
            "modeli fp32 olarak göm. Denklik kapısı düştüğünde kaçış yolu: imaj "
            "büyür ama vektör uzayı indekstekiyle birebir aynı kalır."
        ),
    )
    args = parser.parse_args()

    cache_dir: Path = args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_download:
        _download(cache_dir, args.model)

    snapshot = _snapshot_dir(cache_dir)
    _log(f"anlık görüntü: {snapshot}")

    if args.no_quantize:
        # fp32 yolu: ölçülecek sapma yoktur, model indekstekiyle aynı uzaydadır.
        # İmaj büyür; ama "büyük ve doğru", "küçük ve sessizce yanlış"tan iyidir.
        external = snapshot / "model.onnx_data"
        total = (snapshot / "model.onnx").stat().st_size + (
            external.stat().st_size if external.exists() else 0
        )
        _log(f"quantizasyon ATLANDI; fp32 gömülüyor ({total / 1e9:.2f} GB)")
        _embed(cache_dir, args.model)  # modelin gerçekten yüklendiğini kanıtlar
        if args.report:
            args.report.write_text(
                json.dumps(
                    {"model": args.model, "quantized": False, "fp32_bytes": total},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return 0

    _log("fp32 referans embedding'leri üretiliyor")
    fp32_vectors = _embed(cache_dir, args.model)

    fp32_bytes, int8_bytes = _quantize(snapshot)
    _swap_in_int8(snapshot, cache_dir)
    _prune_blobs(cache_dir)

    _log("int8 embedding'leri üretiliyor")
    int8_vectors = _embed(cache_dir, args.model)

    similarities = [
        _cosine(fp32, int8) for fp32, int8 in zip(fp32_vectors, int8_vectors, strict=True)
    ]
    minimum = min(similarities)
    mean = sum(similarities) / len(similarities)

    # Sıralama korunuyor mu: quantizasyon mutlak değerleri kaydırsa bile retrieval
    # yalnız SIRAYA duyarlıdır. Metinler arası benzerlik sırası değişmediyse indeks
    # anlamını korur. Yüksek kosinüsün tek başına söylemediği şey budur.
    order_fp32 = _neighbour_order(fp32_vectors)
    order_int8 = _neighbour_order(int8_vectors)
    order_preserved = order_fp32 == order_int8

    report = {
        "model": args.model,
        "probe_count": len(PROBE_TEXTS),
        "cosine_min": round(minimum, 6),
        "cosine_mean": round(mean, 6),
        "cosine_all": [round(value, 6) for value in similarities],
        "nearest_neighbour_order_preserved": order_preserved,
        "fp32_bytes": fp32_bytes,
        "int8_bytes": int8_bytes,
        "size_ratio": round(int8_bytes / fp32_bytes, 4) if fp32_bytes else None,
        "min_cosine_threshold": args.min_cosine,
    }
    _log(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if minimum < args.min_cosine:
        _log(
            f"BAŞARISIZ: en düşük kosinüs {minimum:.6f} < {args.min_cosine}. "
            "int8 modeli fp32 ile aynı uzayda değil; korpus int8 ile yeniden "
            "işlenmeden bu imaj kullanılamaz."
        )
        return 1

    _log(f"TAMAM: en düşük kosinüs {minimum:.6f} ≥ {args.min_cosine}")
    return 0


def _neighbour_order(vectors: list[list[float]]) -> list[list[int]]:
    """Her metnin diğerlerine benzerlik sırası."""
    order = []
    for index, vector in enumerate(vectors):
        scored = [
            (_cosine(vector, other), other_index)
            for other_index, other in enumerate(vectors)
            if other_index != index
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        order.append([other_index for _, other_index in scored])
    return order


if __name__ == "__main__":
    sys.exit(main())
