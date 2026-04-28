from typing import List, Optional
from translator_utils import is_russian

class BaseHandler:
    def __init__(self, client, lock):
        self.client = client
        self.lock = lock

    def translate_text_if_russian(self, text: str, max_chunk_chars: int = 4000) -> Optional[str]:
        if not text or not text.strip():
            return None
        
        # If the client is set to the target language, skip
        if self.client.source_lang == self.client.target_lang:
            return None
            
        # For 'ru', we can still use the fast Cyrillic check
        if self.client.source_lang == 'ru' and not is_russian(text):
            return None

        chunks = self._chunk_text(text, max_chunk_chars)
        out = []
        for c in chunks:
            if is_russian(c):
                out.append(self.client.translate(c))
            else:
                out.append(c)
        return "".join(out)

    def _chunk_text(self, text: str, max_chunk_chars: int) -> List[str]:
        if len(text) <= max_chunk_chars:
            return [text]

        import re
        parts = re.split(r"(\n\s*\n)", text)
        chunks: List[str] = []
        buf: str = ""

        for part in parts:
            if len(buf) + len(part) <= max_chunk_chars:
                buf += part
            else:
                if buf:
                    chunks.append(buf)
                    buf = ""
                if len(part) <= max_chunk_chars:
                    buf = part
                else:
                    for i in range(0, len(part), max_chunk_chars):
                        chunks.append(part[i : i + max_chunk_chars])
        if buf:
            chunks.append(buf)
        return chunks
