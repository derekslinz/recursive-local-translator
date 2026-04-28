import os
import threading
from pathlib import Path
from translator.pass_rename import RenameProcessor

class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.mapping = {
            "Привет": "Hello",
            "мир": "world",
            "Папка": "Folder",
            "Иван": "Ivan",
            "Описание": "Description"
        }

    def translate(self, text):
        if text in self.mapping:
            return self.mapping[text]
        if text.startswith("TR_"):
            return text
        return f"TR_{text}"

def mock_unique_path(path: Path) -> Path:
    return path

def test_translate_filename():
    lock = threading.RLock()
    processor = RenameProcessor(MockClient(), lock, mock_unique_path, auto_detect=False)
    
    assert processor.translate_filename("Привет.txt") == "Hello.txt"
    assert processor.translate_filename("Hello.txt") == "Hello.txt"
    assert processor.translate_filename(".hidden") == ".hidden"

def test_process_dirs_recursive(tmp_path):
    lock = threading.RLock()
    processor = RenameProcessor(MockClient(), lock, mock_unique_path, auto_detect=False)
    
    ru_dir = tmp_path / "Папка"
    ru_dir.mkdir()
    (ru_dir / "Привет.txt").write_text("Hello")
    (ru_dir / ".hidden_file").write_text("Hidden")
    
    stats = {}
    def mock_stats_callback(key):
        stats[key] = stats.get(key, 0) + 1
        
    processor.process_dirs_recursive(tmp_path, mock_stats_callback)
    
    # "Папка" -> "Folder"
    assert not (tmp_path / "Папка").exists()
    assert (tmp_path / "Folder").exists()
    # "Привет.txt" -> "Hello.txt"
    assert (tmp_path / "Folder" / "Hello.txt").exists()
    assert (tmp_path / "Folder" / ".hidden_file").exists()

def test_filename_too_long():
    lock = threading.RLock()
    processor = RenameProcessor(MockClient(), lock, mock_unique_path, auto_detect=False)
    
    long_name = "Привет" * 50 + ".txt"
    new_name = processor.translate_filename(long_name)
    assert len(os.fsencode(new_name)) <= 255
    assert new_name.endswith(".txt")
