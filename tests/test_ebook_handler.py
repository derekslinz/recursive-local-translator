import threading
import zipfile

from translator.handlers_ebook import EbookHandler


class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate(self, text):
        return text.replace("Привет", "Hello")


def test_translate_epub_inplace(tmp_path):
    path = tmp_path / "book.epub"

    container_xml = """<?xml version=\"1.0\"?>
<container xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\" version=\"1.0\">
  <rootfiles>
    <rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/>
  </rootfiles>
</container>"""

    opf_xml = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"2.0\">
  <manifest>
    <item id=\"chap1\" href=\"chapter1.xhtml\" media-type=\"application/xhtml+xml\"/>
  </manifest>
  <spine>
    <itemref idref=\"chap1\"/>
  </spine>
</package>"""

    chapter = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<html xmlns=\"http://www.w3.org/1999/xhtml\"><body><p>Привет книга</p></body></html>"""

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf_xml)
        zf.writestr("OEBPS/chapter1.xhtml", chapter)

    handler = EbookHandler(MockClient(), threading.RLock())
    assert handler.translate_epub_inplace(path)

    with zipfile.ZipFile(path, "r") as zf:
        info = zf.infolist()
        assert info[0].filename == "mimetype"
        assert info[0].compress_type == zipfile.ZIP_STORED
        translated = zf.read("OEBPS/chapter1.xhtml").decode("utf-8", errors="ignore")
        assert "Hello книга" in translated
