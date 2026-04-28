from translator.handlers_base import BaseHandler

class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate(self, text):
        return f"[EN:{text}]"

def test_chunk_text():
    handler = BaseHandler(MockClient(), None)
    text = "Line 1\n\nLine 2\n\nLine 3"
    chunks = handler._chunk_text(text, max_chunk_chars=15)
    # Check that it splits roughly by paragraph
    assert len(chunks) >= 2

def test_translate_text_if_russian():
    handler = BaseHandler(MockClient(), None)
    result = handler.translate_text_if_russian("Hello\n\nПривет")
    # "Hello" is not Russian, so it's kept as is. "Привет" is Russian, so it gets translated.
    assert "Hello" in result
    assert "[EN:\n\nПривет]" in result or "[EN:Привет]" in result

def test_translate_text_skips_non_russian():
    handler = BaseHandler(MockClient(), None)
    result = handler.translate_text_if_russian("Just English and numbers 123")
    assert result is None
