"""Sınav provası uçları — Faz D (T032).

ISKELET. Router burada tanımlı ve `main.py`'ye ZATEN kayıtlı; bu dosyayı
sahiplenen oturum yalnız GÖVDE ekler, `main.py`'ye dokunmaz.

Neden böyle: beş oturum paralel çalışıyor ve her biri kendi router'ını
`main.py`'ye eklemeye kalksaydı, aynı iki satır beş kez çakışırdı. Kayıt
işi bir kez, önden yapıldı.

Uç eklerken: OpenAPI sözleşmesi (`specs/001-course-assistant-mvp/contracts/openapi.json`)
oturumun SONUNDA bir kez yeniden export edilir — her uçta değil.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/courses/{course_id}", tags=["exams"])
