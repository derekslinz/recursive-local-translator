import json
import csv
from pathlib import Path
import threading
from translator.handlers_text import TextHandler

class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate(self, text):
        return f"EN_{text}"

def test_json_translation(tmp_path):
    lock = threading.RLock()
    handler = TextHandler(MockClient(), lock)
    
    json_path = tmp_path / "test.json"
    data = {"key": "Привет", "nested": ["мир", "hello"]}
    json_path.write_text(json.dumps(data, ensure_ascii=False))
    
    assert handler.translate_json_inplace(json_path)
    
    new_data = json.loads(json_path.read_text())
    assert new_data["key"] == "EN_Привет"
    assert new_data["nested"][0] == "EN_мир"
    assert new_data["nested"][1] == "hello"  # Not russian

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
        assert reader[1][1] == "EN_Иван"
        assert reader[1][2] == "EN_Описание"
        assert reader[2][1] == "John"
