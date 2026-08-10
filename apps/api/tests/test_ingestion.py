"""Ingestion testleri: doğrulama, ayrıştırma, chunking ve uçtan uca yükleme.

Testler gerçek PDF ve PPTX dosyaları üretir; sahte baytlarla çalışmak, parser'ların
sayfa/slayt numarasını doğru taşıdığını kanıtlamaz — ki sistemin tüm atıf vaadi buna
dayanıyor.
"""

from __future__ import annotations

import itertools
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.errors import PayloadTooLargeError, ValidationError
from app.models.core import ChunkContentType
from app.modules.ingestion import parsers
from app.modules.ingestion.chunking import chunk_blocks, estimate_tokens
from app.modules.ingestion.parsers import ParsedBlock
from app.modules.ingestion.validation import validate_upload
from tests.factories import make_pdf, make_pptx

ALLOWED = {".pdf", ".pptx", ".md", ".txt", ".py"}
MAX_BYTES = 1024 * 1024


class TestValidation:
    def _validate(self, name: str, content: bytes) -> object:
        return validate_upload(
            file_name=name,
            content=content,
            course_id="c0000000-0000-0000-0000-000000000001",
            allowed_extensions=ALLOWED,
            max_bytes=MAX_BYTES,
        )

    def test_gecerli_pdf_kabul_edilir(self) -> None:
        upload = self._validate("hafta3.pdf", make_pdf(["Deadlock"]))
        assert upload.extension == ".pdf"
        assert len(upload.sha256) == 64

    def test_desteklenmeyen_uzanti_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            self._validate("virus.exe", b"MZ\x90\x00")

    def test_uzantisi_degistirilmis_dosya_reddedilir(self) -> None:
        """`.pdf` adı verilmiş çalıştırılabilir dosya sihirli bayt kontrolüne takılır."""
        with pytest.raises(ValidationError, match="uyuşmuyor"):
            self._validate("zararli.pdf", b"MZ\x90\x00" + b"\x00" * 100)

    def test_bos_dosya_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            self._validate("bos.md", b"")

    def test_buyuk_dosya_reddedilir(self) -> None:
        with pytest.raises(PayloadTooLargeError):
            self._validate("buyuk.md", b"a" * (MAX_BYTES + 1))

    def test_utf8_olmayan_metin_reddedilir(self) -> None:
        with pytest.raises(ValidationError, match="UTF-8"):
            self._validate("bozuk.md", b"\xff\xfe\x00bad")

    def test_dizin_gecisi_dosya_adinda_etkisiz(self) -> None:
        upload = self._validate("../../../../etc/passwd.md", b"# not")
        assert ".." not in upload.storage_key
        assert upload.original_name == "passwd.md"
        assert upload.storage_key.startswith("courses/c0000000-")

    def test_ayni_icerik_ayni_hash(self) -> None:
        first = self._validate("a.md", b"# ayni")
        second = self._validate("b.md", b"# ayni")
        assert first.sha256 == second.sha256
        # Depolama anahtarı yine de benzersizdir; dosyalar birbirini ezmez.
        assert first.storage_key != second.storage_key


class TestParsers:
    def test_pdf_sayfa_numaralarini_korur(self) -> None:
        parsed = parsers.parse(make_pdf(["Birinci sayfa metni", "Ikinci sayfa metni"]), ".pdf")
        assert parsed.page_count == 2
        assert [block.page_number for block in parsed.blocks] == [1, 2]
        assert "Birinci" in parsed.blocks[0].text

    def test_metinsiz_pdf_anlasilir_hata_verir(self) -> None:
        import pymupdf

        document = pymupdf.open()
        document.new_page()
        empty = document.tobytes()
        document.close()
        with pytest.raises(ValidationError, match="Taranmış"):
            parsers.parse(empty, ".pdf")

    def test_pptx_slayt_numarasi_ve_basligi_korur(self) -> None:
        parsed = parsers.parse(
            make_pptx([("Deadlock", "Dort kosul"), ("Semafor", "Karsilikli dislama")]),
            ".pptx",
        )
        slides = [block.slide_number for block in parsed.blocks]
        assert slides == [1, 2]
        assert parsed.blocks[0].section_title == "Deadlock"
        assert parsed.blocks[0].page_number is None

    def test_markdown_baslik_hiyerarsisini_tasir(self) -> None:
        content = b"# Isletim Sistemleri\n\nGiris metni.\n\n## Deadlock\n\nDort kosul vardir.\n"
        parsed = parsers.parse(content, ".md")
        titles = [block.section_title for block in parsed.blocks]
        assert "Isletim Sistemleri" in titles
        assert "Isletim Sistemleri > Deadlock" in titles

    def test_kod_fonksiyon_sinirindan_bolunur(self) -> None:
        code = b"import os\n\n\ndef birinci():\n    return 1\n\n\ndef ikinci():\n    return 2\n"
        parsed = parsers.parse(code, ".py")
        assert all(b.content_type is ChunkContentType.CODE for b in parsed.blocks)
        assert len(parsed.blocks) == 3  # import bloğu + iki fonksiyon
        assert any("birinci" in (b.section_title or "") for b in parsed.blocks)
        assert any("satır" in (b.section_title or "") for b in parsed.blocks)


class TestChunking:
    def test_chunk_iki_sayfayi_birlestirmez(self) -> None:
        """Atıf doğruluğunun temeli: bir chunk tek bir sayfaya aittir."""
        blocks = [
            ParsedBlock(text="Sayfa bir metni. " * 5, page_number=1),
            ParsedBlock(text="Sayfa iki metni. " * 5, page_number=2),
        ]
        chunks = chunk_blocks(blocks)
        for chunk in chunks:
            assert chunk.page_number in (1, 2)
        pages = {chunk.page_number for chunk in chunks}
        assert pages == {1, 2}
        for chunk in chunks:
            if chunk.page_number == 1:
                assert "iki" not in chunk.text
            else:
                assert "bir" not in chunk.text

    def test_uzun_metin_bolunur_ve_ortusur(self) -> None:
        sentences = " ".join(f"Bu {i}. cumledir ve makul uzunluktadir." for i in range(200))
        chunks = chunk_blocks([ParsedBlock(text=sentences, page_number=1)])
        assert len(chunks) > 1
        assert all(chunk.token_count <= 700 for chunk in chunks)
        # Örtüşme: ardışık chunk'lar ortak metin paylaşır.
        assert any(set(a.text.split()) & set(b.text.split()) for a, b in itertools.pairwise(chunks))

    def test_kisa_metin_tek_chunk(self) -> None:
        chunks = chunk_blocks([ParsedBlock(text="Kisa bir not.", page_number=3)])
        assert len(chunks) == 1
        assert chunks[0].page_number == 3

    def test_slayt_bilgisi_tasinir(self) -> None:
        chunks = chunk_blocks(
            [ParsedBlock(text="Slayt icerigi.", slide_number=7, section_title="Deadlock")]
        )
        assert chunks[0].slide_number == 7
        assert chunks[0].section_title == "Deadlock"

    def test_token_tahmini_makul(self) -> None:
        assert 1 <= estimate_tokens("kisa") <= 3
        assert estimate_tokens("a" * 370) == pytest.approx(100, abs=5)


class TestRetryBackoff:
    async def test_ilk_hata_veritabanina_gelecek_deneme_zamanini_yazar(self) -> None:
        """Geri çekilme yalnız süreç içi sleep değil, ortak DB kuralıdır."""
        from app.modules.ingestion import pipeline

        session = AsyncMock()
        delay = await pipeline._fail_job(
            session,
            uuid4(),
            uuid4(),
            attempt=1,
            message="geçici hata",
        )

        assert delay == pipeline.RETRY_BACKOFF_SECONDS[0]
        params = session.execute.await_args.args[1]
        assert params["status"] == "pending"
        assert params["delay_seconds"] == pipeline.RETRY_BACKOFF_SECONDS[0]
        assert params["exhausted"] is False
