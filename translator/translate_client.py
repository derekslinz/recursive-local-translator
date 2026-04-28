import sqlite3
import threading
import time
from pathlib import Path
import ctranslate2
import sentencepiece as spm


class DirectTranslateClient:
    """Translate using CTranslate2 + SentencePiece directly on CUDA.

    Bypasses the argostranslate wrapper (which pulls in Stanza/PyTorch
    and makes network calls at import time) and drives the same underlying
    model files installed by `argospm`.
    """

    # Base locations for packages
    _PKG_BASE_LOCATIONS = [
        Path.home() / ".local/share/argos-translate/packages",
        Path("/root/.local/share/argos-translate/packages"),
    ]

    def __init__(
        self,
        cache_file: str = ".translation_cache.db",
        device: str = "cuda",
        pkg_path: str = "",
        source_lang: str = "ru",
        target_lang: str = "en",
        transliterate_only: bool = False,
    ):
        self.device = device
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.transliterate_only = transliterate_only
        self._translator = None
        self._sp = None

        # Discover package path if not provided
        self.pkg_path = pkg_path or self._discover_pkg(source_lang, target_lang)

        self.cache_file = cache_file
        self._db_lock = threading.Lock()
        self.db = sqlite3.connect(self.cache_file, check_same_thread=False, timeout=30)
        with self._db_lock:
            self.db.execute("PRAGMA journal_mode=WAL;")
            self.db.execute("PRAGMA synchronous=NORMAL;")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS translations "
                "(source TEXT PRIMARY KEY, target TEXT)"
            )
            self.db.commit()

    def _discover_pkg(self, source: str, target: str) -> str:
        """Find the Argos Translate package for the given language pair."""
        prefix = f"translate-{source}_{target}"
        for base in self._PKG_BASE_LOCATIONS:
            if not base.is_dir():
                continue
            for d in base.iterdir():
                if d.is_dir() and d.name.startswith(prefix):
                    return str(d)

        # Default fallback (might not exist, but keeps old logic's behavior for RU/EN)
        return str(self._PKG_BASE_LOCATIONS[0] / f"translate-{source}_{target}-1_9")

    def ensure_ready(self, max_wait_s: int = 120):
        """Load the CTranslate2 model and SentencePiece tokenizer."""
        if self.transliterate_only:
            return
        if self._translator is not None:
            return

        model_path = f"{self.pkg_path}/model"
        sp_path = f"{self.pkg_path}/sentencepiece.model"

        if not Path(model_path).is_dir():
            raise RuntimeError(
                f"Model not found at {model_path}. "
                f"Install with: argospm install translate-ru_en"
            )

        if self.device == "auto":
            if ctranslate2.get_cuda_device_count() > 0:
                actual_device = "cuda"
            else:
                try:
                    import torch

                    if torch.backends.mps.is_available():
                        actual_device = "mps"
                    else:
                        actual_device = "cpu"
                except ImportError:
                    actual_device = "cpu"
        elif self.device == "cuda":
            if ctranslate2.get_cuda_device_count() > 0:
                actual_device = "cuda"
            else:
                actual_device = "cpu"
        elif self.device == "mps":
            actual_device = "mps"
        else:
            actual_device = "cpu"

        try:
            self._translator = ctranslate2.Translator(
                model_path,
                device=actual_device,
                compute_type="auto",
            )
        except ValueError as e:
            if actual_device in ("mps", "cuda") and (
                "unsupported device" in str(e).lower() or "not found" in str(e).lower()
            ):
                fallback_reason = (
                    "not supported by CTranslate2"
                    if actual_device == "mps"
                    else "not available"
                )
                print(
                    f"  ℹ {actual_device.upper()} requested/detected but {fallback_reason}. Falling back to CPU."
                )
                actual_device = "cpu"
                self._translator = ctranslate2.Translator(
                    model_path,
                    device=actual_device,
                    compute_type="auto",
                )
            else:
                raise

        self._sp = spm.SentencePieceProcessor(sp_path)
        self.device = actual_device
        print(f"Success: CTranslate2 ready ({actual_device})")

    def translate(
        self,
        text: str,
        source_lang: str = "ru",
        target_lang: str = "en",
        retry: int = 3,
    ) -> str:
        """Translate text using CTranslate2 + SentencePiece or transliterate."""
        text = text.encode("utf-8", "surrogateescape").decode("utf-8", "ignore")
        if not text or not text.strip():
            return text

        if self.transliterate_only:
            from .translator_utils import transliterate_text

            return transliterate_text(text)

        with self._db_lock:
            cur = self.db.execute(
                "SELECT target FROM translations WHERE source = ?", (text,)
            )
            row = cur.fetchone()
            if row:
                return row[0]

        for attempt in range(retry):
            try:
                tokens = self._sp.encode(text, out_type=str)
                results = self._translator.translate_batch([tokens])
                translated = self._sp.decode(results[0].hypotheses[0])

                with self._db_lock:
                    self.db.execute(
                        "INSERT OR IGNORE INTO translations "
                        "(source, target) VALUES (?, ?)",
                        (text, translated),
                    )
                    self.db.commit()
                return translated

            except Exception as e:
                print(f"  Warning: Translation error for '{text[:50]}...': {e}")
                time.sleep(0.5)
        return text
