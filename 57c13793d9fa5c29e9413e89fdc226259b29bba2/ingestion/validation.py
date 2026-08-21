"""Yükleme doğrulaması.

Güvenlik gereği (ARCHITECTURE.md §6) uzantıya güvenilmez: dosyanın ilk baytları da
beyan edilen türle tutarlı olmalıdır. Böylece `.pdf` adı verilmiş bir çalıştırılabilir
dosya parser'a hiç ulaşmaz.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.errors import PayloadTooLargeError, ValidationError

# Uzantı -> kabul edilen sihirli bayt önekleri. Boş demet: ikili imza aranmaz,
# bunun yerine içeriğin UTF-8 çözülebilir olması beklenir.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".pptx": (b"PK\x03\x04",),  # OpenXML = zip
    ".md": (),
    ".txt": (),
    ".py": (),
    ".java": (),
    ".js": (),
    ".ts": (),
    ".c": (),
    ".h": (),
    ".cpp": (),
}

TEXT_EXTENSIONS = frozenset(ext for ext, magic in _MAGIC_BYTES.items() if not magic)
CODE_EXTENSIONS = frozenset({".py", ".java", ".js", ".ts", ".c", ".h", ".cpp"})


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """Doğrulanmış yükleme.

    `storage_key` kullanıcıdan gelen adı içermez; dosya adı disk yoluna hiç
    dönüşmediği için dizin geçişi (path traversal) mümkün olmaz.
    """

    original_name: str
    extension: str
    content: bytes
    sha256: str
    storage_key: str

    @property
    def byte_size(self) -> int:
        return len(self.content)


def _safe_display_name(raw: str) -> str:
    """Dosya adını yalnızca GÖSTERİM için temizler; yol olarak asla kullanılmaz."""
    name = PurePosixPath(raw.replace("\\", "/")).name
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '\\/:*?"<>|')
    name = name.strip(" .")
    return name[:200] or "belge"


def validate_upload(
    *,
    file_name: str,
    content: bytes,
    course_id: str,
    allowed_extensions: set[str],
    max_bytes: int,
) -> ValidatedUpload:
    display_name = _safe_display_name(file_name)
    extension = PurePosixPath(display_name).suffix.lower()

    if extension not in allowed_extensions or extension not in _MAGIC_BYTES:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"Desteklenmeyen dosya türü. İzin verilenler: {allowed}")

    if not content:
        raise ValidationError("Dosya boş görünüyor.")

    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise PayloadTooLargeError(f"Dosya çok büyük. En fazla {limit_mb} MB yükleyebilirsiniz.")

    expected_magic = _MAGIC_BYTES[extension]
    if expected_magic:
        if not content.startswith(expected_magic):
            raise ValidationError(
                f"Dosya içeriği {extension} biçimiyle uyuşmuyor. "
                "Dosyanın bozuk olmadığından emin olun."
            )
    else:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(
                "Metin dosyası UTF-8 olarak okunamadı. Dosyayı UTF-8 kaydedip tekrar deneyin."
            ) from exc

    digest = hashlib.sha256(content).hexdigest()
    # Depolama anahtarı tamamen sunucu üretimi: ders klasörü + rastgele kimlik.
    storage_key = f"courses/{course_id}/{uuid4().hex}{extension}"

    return ValidatedUpload(
        original_name=display_name,
        extension=extension,
        content=content,
        sha256=digest,
        storage_key=storage_key,
    )
