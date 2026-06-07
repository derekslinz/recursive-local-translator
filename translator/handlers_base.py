from typing import Optional
import re as _re
from .translator_utils import is_russian

_SENT_SPLIT_RE = _re.compile(r'(?<=[.!?…])\s+(?=[A-ZА-ЯЁ"\(\[])')
_SENT_THRESH = 500  # chars; paragraphs shorter than this go as-is


class BaseHandler:
    def __init__(self, client, lock):
        self.client = client
        self.lock = lock

    def _split_sentences(self, text: str) -> list:
        if len(text) <= _SENT_THRESH:
            return [text]
        parts = _SENT_SPLIT_RE.split(text)
        return parts if len(parts) > 1 else [text]

    def translate_text_if_russian(
        self, text: str, max_chunk_chars: int = 4000
    ) -> Optional[str]:
        if not text or not text.strip():
            return None

        if self.client.source_lang == self.client.target_lang:
            return None

        import re

        # Split by paragraph while keeping the separators
        parts = re.split(r"(\n\s*\n)", text)
        out = []
        any_translated = False

        for p in parts:
            if not p:
                continue
            if is_russian(p):
                # If a part is too long, we still need to chunk it for the model
                if len(p) > max_chunk_chars:
                    subchunks = [
                        p[i : i + max_chunk_chars]
                        for i in range(0, len(p), max_chunk_chars)
                    ]
                    for sc in subchunks:
                        if is_russian(sc):
                            out.append(self.client.translate(sc))
                            any_translated = True
                        else:
                            out.append(sc)
                else:
                    sentences = self._split_sentences(p)
                    if len(sentences) == 1:
                        out.append(self.client.translate(p))
                    else:
                        translated_sentences = []
                        for sent in sentences:
                            if is_russian(sent):
                                translated_sentences.append(self.client.translate(sent))
                            else:
                                translated_sentences.append(sent)
                        out.append(" ".join(translated_sentences))
                    any_translated = True
            else:
                out.append(p)

        if not any_translated:
            return None
        return "".join(out)
