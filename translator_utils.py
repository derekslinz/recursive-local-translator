import re
import os
import errno
import shutil
from pathlib import Path
from typing import Tuple, Optional
try:
    from langdetect import detect as ld_detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

# Regex for Cyrillic characters
CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")

# Regex for generic titles to avoid as filenames
GENERIC_TITLE_RE = re.compile(
    r"^(?:document|file|scan|image|note|untitled|new\s+file|"
    r"page|report|log|result|data|export|copy|doc|"
    r"presentation|slide|sheet|book)(?:\b|$)",
    re.IGNORECASE,
)

def is_russian(s: str) -> bool:
    """Check if a string contains any Cyrillic characters."""
    if not s:
        return False
    # Sanitize surrogates to prevent UnicodeEncodeError in regex/json
    s = s.encode("utf-8", "surrogateescape").decode("utf-8", "ignore")
    return bool(CYRILLIC_RE.search(s))

def detect_language(text: str) -> str:
    """Detect the language of the given text, falling back to 'ru' if detection fails or is unavailable."""
    if not text or not text.strip():
        return "ru"
    if not HAS_LANGDETECT:
        return "ru" if is_russian(text) else "en"
    try:
        # Sanitize text for langdetect
        clean_text = text.encode("utf-8", "surrogateescape").decode("utf-8", "ignore")
        return ld_detect(clean_text)
    except Exception:
        return "ru" if is_russian(text) else "en"

def sanitize_name(name: str) -> str:
    """Remove invalid characters and collapse excessive repetitions."""
    # Remove invalid filesystem characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Collapse repeating characters (e.g., __________ -> _)
    name = re.sub(r"(.)\1{4,}", r"\1", name)
    if len(name) > 255:
        name = name[:255].rstrip()
    return name

def split_suffixes(name: str) -> Tuple[str, str]:
    """Split filename into stem and all suffixes."""
    p = Path(name)
    suffixes = p.suffixes
    if not suffixes:
        return name, ""
    suf = "".join(suffixes)
    stem = name[: -len(suf)]
    return stem, suf

def needs_content_based_name(stem: str) -> bool:
    """Check if the filename is generic enough to warrant renaming based on content."""
    clean = stem.strip()
    if not clean:
        return True
    lower = clean.lower()
    if lower.isdigit():
        return True
    if len(clean) <= 2:
        return True
    if GENERIC_TITLE_RE.match(lower):
        return True
    return False

def safe_exists(path: Path) -> bool:
    """Safely check if a path exists."""
    try:
        return path.exists()
    except OSError:
        return False

def safe_is_file(path: Path) -> bool:
    """Safely check if path is a file."""
    try:
        return path.is_file()
    except OSError:
        return False

def safe_is_dir(path: Path) -> bool:
    """Safely check if path is a directory."""
    try:
        return path.is_dir()
    except OSError:
        return False

def move_path(src: Path, dst: Path) -> None:
    """Move path, handling cross-device links."""
    try:
        src.rename(dst)
    except OSError as e:
        if e.errno == errno.EXDEV:
            shutil.move(str(src), str(dst))
        else:
            raise
