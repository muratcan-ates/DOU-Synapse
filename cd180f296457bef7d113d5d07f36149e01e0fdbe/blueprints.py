"""Sınav blueprint uçları — 002 US3 (T504).

**Bu modül bugün bilerek boştur ve bir yol tanımlamaz.**

Lider turunda önden oluşturuldu çünkü router kaydı `main.py`'de yaşıyor ve
`main.py` üç şeridin birden dokunacağı bir dosya. Blueprint şeridi açıldığında
buraya uç eklemesi yetecek; `main.py`'ye hiç dokunmayacak. Bu, 001'in Faz 2
turunda ölçülmüş bir dersin uygulanması: "ortak dosyalar önden düzenlenir — iki
şeridin dokunacağı her şeyi tur başlamadan lider bir kez düzenler" (devir
belgesi §7). O turda bu yapıldığında tek bir gerçek çakışma çıkmıştı.

Boş router'ın yol sayısını değiştirmediği testle sabitlenmiştir: kayıtlı ama boş
bir router, OpenAPI sözleşmesini bugün büyütmemelidir — sözleşme 26 yolda kalır
(`specs/001-course-assistant-mvp/contracts/openapi.json`). Blueprint şeridi ilk
ucunu eklediğinde o testi kendi beklentisine göre günceller.

Yol öneki `/courses/{course_id}` altındadır ve yetkilendirme `CourseInstructorDep`
ile yapılır: blueprint öğretmenin aracıdır, öğrenci taslak bir sınavı görmez
(FR-111). Prefix burada sabitlendi ki iki şerit iki farklı yol şeması yazmasın.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/courses/{course_id}", tags=["blueprints"])
