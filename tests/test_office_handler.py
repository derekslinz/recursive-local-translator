import io
import threading
import zipfile

from translator.handlers_office import OfficeHandler


class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate(self, text):
        return text.replace("Привет", "Hello")


def test_translate_odf_inplace(tmp_path):
    content_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<office:document-content xmlns:office=\"urn:oasis:names:tc:opendocument:xmlns:office:1.0\" xmlns:text=\"urn:oasis:names:tc:opendocument:xmlns:text:1.0\">
  <office:body><office:text><text:p>Привет мир</text:p></office:text></office:body>
</office:document-content>""".encode("utf-8")

    path = tmp_path / "sample.odt"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("content.xml", content_xml)
        zf.writestr("META-INF/manifest.xml", "<manifest/>")

    handler = OfficeHandler(MockClient(), threading.RLock())
    assert handler.translate_odf_inplace(path)

    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        assert "content.xml" in names
        assert "META-INF/manifest.xml" in names
        translated = zf.read("content.xml").decode("utf-8", errors="ignore")
        assert "Hello мир" in translated
