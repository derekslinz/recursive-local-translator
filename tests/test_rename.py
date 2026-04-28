import os
import threading
from pathlib import Path
from translator.pass_rename import RenameProcessor

class MockClient:
    def __init__(self, source_lang="ru", target_lang="en"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def translate(self, text):
        return f"EN_{text}"

def mock_unique_path(path: Path) -> Path:
    return path

def test_translate_filename():
    lock = threading.RLock()
    processor = RenameProcessor(MockClient(), lock, mock_unique_path, auto_detect=False)
    
    # "Привет.txt" is Russian, so it gets translated to "EN_Привет" and then sanitized.
    # sanitize_name will replace spaces and special characters.
    assert processor.translate_filename("Привет.txt") == "EN_Привет.txt"
    assert processor.translate_filename("Hello.txt") == "Hello.txt" # Not Russian, no translation
    
    # Test hidden files (should be skipped)
    assert processor.translate_filename(".hidden") == ".hidden"
    assert processor.translate_filename("..") == ".."

def test_process_dirs_recursive(tmp_path):
    lock = threading.RLock()
    processor = RenameProcessor(MockClient(), lock, mock_unique_path, auto_detect=False)
    
    # Create test directory structure
    ru_dir = tmp_path / "Папка"
    ru_dir.mkdir()
    (ru_dir / "Привет.txt").write_text("Hello")
    (ru_dir / ".hidden_file").write_text("Hidden")
    
    stats = {"files_renamed": 0, "items_moved": 0, "dirs_created": 0}
    def mock_stats_callback(key):
        stats[key] = stats.get(key, 0) + 1
        
    processor.process_dirs_recursive(tmp_path, mock_stats_callback)
    
    # Check directory was renamed
    assert not (tmp_path / "Папка").exists()
    assert (tmp_path / "EN_Папка").exists()
    
    # Check file was renamed
    assert (tmp_path / "EN_Папка" / "EN_Привет.txt").exists()
    assert (tmp_path / "EN_Папка" / ".hidden_file").exists() # Hidden file moved but not renamed
    
    assert stats["dirs_created"] == 1
    assert stats["files_renamed"] == 1
    assert stats["items_moved"] >= 1
