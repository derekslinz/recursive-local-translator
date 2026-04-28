import threading
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from translator.handlers_email import EmailHandler


class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.mapping = {
            "Привет": "Hello",
            "вложение": "attachment",
            "Тема": "Subject",
            "тело": "body",
        }

    def translate(self, text):
        out = text
        for src, dst in self.mapping.items():
            out = out.replace(src, dst)
        return out


def test_eml_translates_body_and_base64_text_attachment(tmp_path):
    msg = EmailMessage()
    msg["Subject"] = "Тема"
    msg["From"] = "sender@example.com"
    msg["To"] = "receiver@example.com"
    msg.set_content("Привет тело")

    msg.add_attachment(
        "Привет вложение",
        subtype="plain",
        filename="notes.txt",
        cte="base64",
    )

    binary_payload = b"\x00\x01\x02\x03BINARY\xff"
    msg.add_attachment(
        binary_payload,
        maintype="application",
        subtype="octet-stream",
        filename="blob.bin",
        cte="base64",
    )

    path = tmp_path / "sample.eml"
    path.write_bytes(msg.as_bytes(policy=policy.default))

    handler = EmailHandler(MockClient(), threading.RLock())
    assert handler.translate_eml_inplace(path)

    parsed = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    assert str(parsed["Subject"]) == "Subject"

    parts = [p for p in parsed.walk() if not p.is_multipart()]
    body_part = next(p for p in parts if p.get_content_disposition() is None)
    assert "Hello body" in body_part.get_payload(decode=True).decode(
        "utf-8", errors="ignore"
    )

    text_attach = next(p for p in parts if p.get_filename() == "notes.txt")
    text_attach_payload = text_attach.get_payload(decode=True).decode(
        "utf-8", errors="ignore"
    )
    assert "Hello attachment" in text_attach_payload

    binary_attach = next(p for p in parts if p.get_filename() == "blob.bin")
    assert binary_attach.get_payload(decode=True) == binary_payload
