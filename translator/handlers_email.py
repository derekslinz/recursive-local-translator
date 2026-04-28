import email
import email.encoders
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Optional, Tuple

from .handlers_base import BaseHandler


class EmailHandler(BaseHandler):
    TEXT_ATTACHMENT_EXTENSIONS = {
        ".txt",
        ".log",
        ".md",
        ".rst",
        ".adoc",
        ".org",
        ".wiki",
        ".rtx",
        ".cfg",
        ".conf",
        ".toml",
        ".properties",
        ".yaml",
        ".yml",
        ".xml",
        ".html",
        ".htm",
        ".xhtml",
        ".shtml",
        ".json",
        ".json5",
        ".jsonc",
        ".jsonl",
        ".csv",
        ".tsv",
        ".srt",
        ".vtt",
        ".ass",
        ".ssa",
        ".sub",
        ".sbv",
        ".po",
        ".pot",
        ".tex",
        ".lrc",
        ".textile",
        ".info",
        ".strings",
        ".arb",
        ".resx",
        ".xliff",
        ".xlf",
        ".tmx",
        ".ts",
        ".fb2",
    }

    def translate_eml_inplace(self, path: Path) -> bool:
        try:
            raw = path.read_bytes()
            msg = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception as e:
            print(f"  Warning: EML parse error: {path}: {e}")
            return False

        changed = False

        subject = msg.get("Subject")
        if subject:
            translated_subject = self.translate_text_if_russian(str(subject))
            if translated_subject is not None and translated_subject != str(subject):
                msg.replace_header("Subject", translated_subject)
                changed = True

        for part in msg.walk():
            if part.is_multipart():
                continue

            if self._is_attachment(part):
                if self._translate_attachment(part):
                    changed = True
                continue

            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue

            payload_text = self._decode_text_payload(part)
            if payload_text is None:
                continue

            translated_payload = self.translate_text_if_russian(payload_text)
            if translated_payload is not None and translated_payload != payload_text:
                self._set_text_payload(part, translated_payload)
                changed = True

        if not changed:
            return False

        try:
            path.write_bytes(msg.as_bytes(policy=policy.default))
            return True
        except Exception as e:
            print(f"  Warning: EML write error: {path}: {e}")
            return False

    def _translate_attachment(self, part: email.message.Message) -> bool:
        transfer_encoding = (part.get("Content-Transfer-Encoding") or "").lower()
        if "base64" not in transfer_encoding:
            return False

        payload_bytes = part.get_payload(decode=True)
        if payload_bytes is None:
            return False

        if not self._is_text_attachment(part):
            return False

        decoded_text, encoding = self._decode_attachment_text(part, payload_bytes)
        if decoded_text is None:
            return False

        translated = self.translate_text_if_russian(decoded_text)
        if translated is None or translated == decoded_text:
            return False

        data = translated.encode("utf-8")
        part.set_payload(data)
        if part.get("Content-Transfer-Encoding"):
            del part["Content-Transfer-Encoding"]
        email.encoders.encode_base64(part)
        part.set_param("charset", "utf-8", header="Content-Type", replace=True)
        if encoding and encoding.lower() != "utf-8":
            part.set_param("original-charset", encoding, header="Content-Type")
        return True

    def _decode_attachment_text(
        self, part: email.message.Message, payload_bytes: bytes
    ) -> Tuple[Optional[str], Optional[str]]:
        preferred = part.get_content_charset()
        tried = []
        candidates = [preferred] if preferred else []
        candidates.extend(["utf-8", "cp1251", "koi8-r", "latin-1"])
        for enc in candidates:
            if not enc or enc in tried:
                continue
            tried.append(enc)
            try:
                return payload_bytes.decode(enc), enc
            except Exception:
                continue
        return None, None

    def _decode_text_payload(self, part: email.message.Message) -> Optional[str]:
        raw = part.get_payload(decode=True)
        if raw is None:
            content = part.get_content()
            return content if isinstance(content, str) else None

        charset = part.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset)
        except Exception:
            for fallback in ("utf-8", "cp1251", "koi8-r", "latin-1"):
                try:
                    return raw.decode(fallback)
                except Exception:
                    continue
        return None

    def _set_text_payload(self, part: email.message.Message, value: str) -> None:
        part.set_payload(value.encode("utf-8"))
        part.set_param("charset", "utf-8", header="Content-Type", replace=True)
        if part.get("Content-Transfer-Encoding"):
            del part["Content-Transfer-Encoding"]
        email.encoders.encode_base64(part)

    def _is_attachment(self, part: email.message.Message) -> bool:
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        return disposition == "attachment" or bool(filename)

    def _is_text_attachment(self, part: email.message.Message) -> bool:
        if part.get_content_maintype() == "text":
            return True
        filename = part.get_filename() or ""
        suffix = Path(filename).suffix.lower()
        return suffix in self.TEXT_ATTACHMENT_EXTENSIONS
