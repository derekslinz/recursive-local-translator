from translator.handlers_base import BaseHandler


class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.mapping = {
            "Привет": "Hello",
            "мир": "world",
            "Папка": "Folder",
            "Иван": "Ivan",
            "Описание": "Description",
        }

    def translate(self, text):
        return self.mapping.get(text, f"TR_{text}")


def test_translate_text_if_russian():
    handler = BaseHandler(MockClient(), None)
    result = handler.translate_text_if_russian("Hello\n\nПривет")
    # "Hello" is not Russian, so it's kept as is. "Привет" is Russian, so it gets translated.
    assert "Hello" in result
    assert "Hello" in result and result.endswith(
        "Hello"
    )  # In this case "Привет" -> "Hello"


def test_translate_text_skips_non_russian():
    handler = BaseHandler(MockClient(), None)
    result = handler.translate_text_if_russian("Just English and numbers 123")
    assert result is None
