import json
import csv
import threading
from translator.handlers_text import TextHandler


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


def test_json_translation(tmp_path):
    lock = threading.RLock()
    handler = TextHandler(MockClient(), lock)

    json_path = tmp_path / "test.json"
    data = {"key": "Привет", "nested": ["мир", "hello"]}
    json_path.write_text(json.dumps(data, ensure_ascii=False))

    assert handler.translate_json_inplace(json_path)

    new_data = json.loads(json_path.read_text())
    assert new_data["key"] == "Hello"
    assert new_data["nested"][0] == "world"
    assert new_data["nested"][1] == "hello"


def test_csv_translation(tmp_path):
    lock = threading.RLock()
    handler = TextHandler(MockClient(), lock)

    csv_path = tmp_path / "test.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "desc"])
        writer.writerow(["1", "Иван", "Описание"])
        writer.writerow(["2", "John", "Description"])

    assert handler.translate_csv_inplace(csv_path)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = list(csv.reader(f))
        assert reader[1][1] == "Ivan"
        assert reader[1][2] == "Description"
        assert reader[2][1] == "John"
