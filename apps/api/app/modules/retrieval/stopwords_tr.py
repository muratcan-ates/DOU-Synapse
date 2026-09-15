"""Kavram çıkarımının eledi̇ği Türkçe işlev sözcükleri.

## Liste neden dar tutuldu

Kolay olan geniş bir "gereksiz kelime" listesi yazmaktır; doğru olan değil.
Türkçede genel görünen pek çok sözcük bilgisayar bilimlerinde **kavramın
kendisidir**: `zaman` (zaman aşımı), `durum` (durum makinesi), `işlem`, `bellek`,
`sonuç`, `kaynak`, `alan`, `konu`. Bunları eleyen bir liste, tam da öğrencinin
görmesi gereken terimleri siler ve bunu sessizce yapar.

Bu yüzden listede yalnız iki tür sözcük var:

1. **İşlev sözcükleri** — bağlaç, edat, zamir, soru sözcüğü ve yardımcı fiil
   çekimleri. Hiçbir alanda kavram değiller.
2. **Belge iskeleti** — `sayfa`, `slayt`, `bölüm`, `şekil`, `tablo` gibi
   materyalin kendisini değil sunumunu anlatan sözcükler.

Alan adı olabilecek hiçbir sözcük burada yoktur. Liste kısa kalmalı: kararı
veren asıl mekanizma eleme değil, `concepts.py` içindeki "en az iki parçada
geçmeli" eşiğidir.

## Biçim

Girdiler `core.text_tr.fold()` çıktısıyla karşılaştırılır, yani ASCII ve
küçük harflidir ("için" → "icin"). Dört karakterden kısa sözcükler zaten
`min_length` eşiğinde elendiği için listeye alınmadı.
"""

from __future__ import annotations

#: Bağlaç, edat, zamir, soru sözcüğü ve yardımcı fiil çekimleri.
_ISLEV_SOZCUKLERI = frozenset(
    {
        "acisindan",
        "alti",
        "arasi",
        "arasinda",
        "altinda",
        "ancak",
        "ayni",
        "ayrica",
        "bakimindan",
        "bazen",
        "bazi",
        "belki",
        "birlikte",
        "bircok",
        "boylece",
        "buna",
        "bunlar",
        "bunlarin",
        "bunun",
        "burada",
        "butun",
        "cogu",
        "cunku",
        "daha",
        "degil",
        "degildir",
        "diger",
        "digeri",
        "dolayi",
        "dolayisiyla",
        "eger",
        "fakat",
        "edilen",
        "edilir",
        "farkli",
        "fazla",
        "genel",
        "genellikle",
        "gerekir",
        "gerekli",
        "gereken",
        "gibi",
        "gore",
        "hangi",
        "hatta",
        "henuz",
        "hepsi",
        "herhangi",
        "hicbir",
        "iceren",
        "icerir",
        "icin",
        "iken",
        "ilgili",
        "iliskin",
        "kadar",
        "kendi",
        "kendisi",
        "kullanilan",
        "kullanilir",
        "kucuk",
        "mesela",
        "nasil",
        "neden",
        "nedeniyle",
        "olabilir",
        "olan",
        "olarak",
        "olmak",
        "olmasi",
        "olmaz",
        "oldugu",
        "oldugunu",
        "olmasini",
        "olup",
        "onlarin",
        "ornegin",
        "oysa",
        "sadece",
        "sahip",
        "sekilde",
        "saglar",
        "saglayan",
        "sonra",
        "soyle",
        "sunlar",
        "sunun",
        "tarafindan",
        "uzere",
        "uzerinde",
        "uzerine",
        "vardir",
        "veya",
        "yalniz",
        "yani",
        "yeni",
        "yine",
        "yoksa",
        "yapilan",
        "yapilir",
        "yoktur",
    }
)

#: Materyalin sunumunu anlatan, içeriğini anlatmayan sözcükler.
#:
#: Liste bilerek ÜÇ sözcüğe indirildi. İlk hâlinde `sayfa`, `tablo`, `şekil` ve
#: `örnek` de vardı ve bu, dosyanın kendi kuralını ("alan adı olabilecek hiçbir
#: sözcük burada yoktur") çiğniyordu: işletim sistemlerinde **sayfa tablosu**,
#: **sayfa hatası** ve **süreç tablosu** kavramın ta kendisidir. Aşağıdaki üçü
#: hangi alanda olursa olsun belgenin sunumunu anlatır.
#:
#: `konu` bilinçli bir karar: ders materyallerinde slayt başlığı olarak geçiyor
#: (demo korpusunda 9 pasajda ölçüldü) ve bir kavram değil. Ürünün `Topic`
#: varlığıyla karıştırılmamalı — o ayrı bir veri modeli.
_BELGE_ISKELETI = frozenset(
    {
        "baslik",
        "bolum",
        "konu",
        "slayt",
    }
)

STOPWORDS: frozenset[str] = _ISLEV_SOZCUKLERI | _BELGE_ISKELETI
