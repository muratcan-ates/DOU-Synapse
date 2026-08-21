"""LLM metninden JSON çıkarma — tek kural.

Sağlayıcılar JSON modunda bile saf JSON döndürmez. Gözlenen üç gürültü biçimi:

    ```json\n{...}\n```          kod çiti
    İşte sorular: {...}          önek cümlesi
    {...}\n\nUmarım yardımcı...  sonek cümlesi

Bu dosya açılmadan önce iki ayrı temizleme kuralı vardı ve ikisi de aynı
sağlayıcıdan aynı gürültüyü alıyordu:

* `generation/service._first_json_object` — metni tarar, ilk geçerli JSON
  nesnesini alır. Üç biçimi de kaldırır.
* `assessment/question_gen.extract_json_object` — yalnız kod çitini sıyırır,
  sonra `json.loads` çağırır. Önek cümlesinde `JSONDecodeError` verir.

Fark kozmetik değildi: sohbet yolunun sorunsuz kabul ettiği bir yanıt, soru
üretimi ve sınav puanlaması yolunda "şema bozuk" sayılıp bir yeniden denemeye
mal oluyordu; ikinci deneme de aynı önekle gelirse soru sessizce düşüyordu.
`grading._parse_verdict`'in docstring'i kuralın ortak olduğunu zaten İDDİA
ediyordu — iddia doğru değildi, artık doğru.

Tarama yaklaşımı kazandı çünkü çit sıyırmanın yaptığı her şeyi zaten yapıyor:
``` ile başlayan bir metinde ilk `{`, çitin içindeki nesnedir.
"""

from __future__ import annotations

import json
from typing import Any

_DECODER = json.JSONDecoder()


def first_json_object(raw: str) -> dict[str, Any] | None:
    """Metindeki ilk geçerli JSON **nesnesini** döndürür; yoksa `None`.

    İstisna DEĞİL `None` döner: her iki çağıran da hatayı bir sebep dizesine
    çeviriyor, yani istisna zaten sınırın bir adım ötesinde yakalanıyordu.
    Sentinel, `try` bloğunun çağıranın niyetini gizlemesini engelliyor.

    Dizi ya da skaler döndüren bir yanıt `None` sayılır: şemalarımızın hepsi
    nesne bekliyor, `[...]` gelmesi ayrıştırma başarısı değil şema hatasıdır.
    """
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = _DECODER.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


__all__ = ["first_json_object"]
