import os
import threading
import time
from pathlib import Path
from typing import List, Optional

from .translate_client import DirectTranslateClient
from .translator_utils import (
    is_russian,
    sanitize_name,
    needs_content_based_name,
    safe_exists,
    safe_is_file,
    safe_is_dir,
    detect_language,
)
from .handlers_text import TextHandler
from .handlers_office import OfficeHandler
from .handlers_media import MediaHandler
from .pass_rename import RenameProcessor


class WorkspaceRUENTranslator:
    def __init__(self, root_path: str, **kwargs):
        self.root_path = Path(root_path)
        self._lock = threading.RLock()

        self.source_lang = kwargs.get("source_lang", "ru")
        self.target_lang = kwargs.get("target_lang", "en")
        self.auto_detect = kwargs.get("auto_detect", False)

        self.client = DirectTranslateClient(
            cache_file=kwargs.get("cache_file", ".translation_cache.db"),
            device=kwargs.get("device", "auto"),
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )
        self.rename_only = kwargs.get("rename_only", False)
        self.upgrade_only = kwargs.get("upgrade_only", False)
        self.translate_extract_sidecars = kwargs.get("translate_extract_sidecars", True)
        self.text_extensions = {
            ".txt",
            ".log",
            ".nfo",
            ".md",
            ".mdx",
            ".rmd",
            ".rst",
            ".adoc",
            ".org",
            ".wiki",
            ".rtx",
            ".cfg",
            ".conf",
            ".toml",
            ".properties",
            ".mak",
            ".cmake",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".htm",
            ".xhtml",
            ".shtml",
            ".json5",
            ".jsonc",
            ".srt",
            ".vtt",
            ".ass",
            ".ssa",
            ".sub",
            ".sbv",
            ".po",
            ".pot",
            ".tex",
        }
        self.image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

        self.text_handler = TextHandler(self.client, self._lock)
        self.office_handler = OfficeHandler(self.client, self._lock)
        self.media_handler = MediaHandler(self.client, self._lock)
        self.rename_proc = RenameProcessor(
            self.client,
            self._lock,
            self._unique_path,
            auto_detect=self.auto_detect,
            target_lang=self.target_lang,
        )

        self.stats = {
            k: 0
            for k in [
                "dirs_created",
                "dirs_existing_merged",
                "items_moved",
                "files_renamed",
                "files_content_translated",
                "files_content_skipped",
                "sidecars_written",
                "files_content_renamed",
            ]
        }

    def _stats_inc(self, key):
        with self._lock:
            self.stats[key] += 1

    def _unique_path(self, path: Path) -> Path:
        with self._lock:
            if not safe_exists(path):
                return path
            suf, stem = path.suffix, path.stem
            while len(os.fsencode(stem)) > 250:
                stem = stem[:-1].rstrip()
            base, i = path.with_name(stem), 1
            while True:
                name = f"{base.name}-{i}{suf}"
                while len(os.fsencode(name)) > 255:
                    stem = base.name[:-1].rstrip()
                    base = base.with_name(stem)
                    name = f"{base.name}-{i}{suf}"
                new_p = path.with_name(name)
                if not safe_exists(new_p):
                    return new_p
                i += 1

    def _maybe_rename_via_content(self, path: Path) -> None:
        if not needs_content_based_name(path.stem):
            return
        snippet = self._get_content_snippet(path)
        if not snippet:
            return
        snippet = snippet.splitlines()[0].strip()

        # Determine source language
        src_lang = self.source_lang
        if self.auto_detect:
            src_lang = detect_language(snippet)
            if src_lang == self.target_lang:
                return  # Already target language

        if is_russian(snippet) or (self.auto_detect and src_lang != self.target_lang):
            # Switch client if needed
            self._ensure_client_lang(src_lang)
            snippet = self.client.translate(snippet)

        snippet = snippet.replace("\n", " ").strip()[:70].rstrip()
        candidate = sanitize_name(snippet)
        if not candidate or candidate == path.stem:
            return
        new_path = self._unique_path(path.with_name(candidate + path.suffix))
        try:
            path.rename(new_path)
            self._stats_inc("files_content_renamed")
            print(f"    ➜ Renamed via content: {new_path.name}")
        except OSError:
            pass

    def _get_content_snippet(self, path: Path) -> Optional[str]:
        suf = path.suffix.lower()
        try:
            if suf in self.text_extensions:
                for line in path.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines():
                    if line.strip():
                        return line.strip()
            if suf in {".csv", ".tsv"}:
                import csv

                with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                    for row in csv.reader(f):
                        for c in row:
                            if c.strip():
                                return c.strip()
            if suf == ".json":
                import json

                return self._find_first_json_string(
                    json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                )
            if suf in (".docx", ".xlsx", ".pptx"):
                # Dynamically import to avoid overhead if not used
                if suf == ".docx":
                    from .handlers_office import HAS_DOCX, DocxDocument

                    if HAS_DOCX:
                        for p in DocxDocument(path).paragraphs:
                            if p.text.strip():
                                return p.text.strip()
                # ... other office formats similar to before
        except Exception:
            pass
        return None

    def _find_first_json_string(self, v) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        if isinstance(v, (list, dict)):
            for i in v if isinstance(v, list) else v.values():
                res = self._find_first_json_string(i)
                if res:
                    return res
        return None

    def _ensure_client_lang(self, source: str) -> None:
        """Ensure the client is ready for the given source language."""
        if self.client.source_lang == source:
            return

        with self._lock:
            # Create a new client for the new language pair
            # In a production setting, we might want to cache clients
            print(f"  ℹ Switching language model: {source} → {self.target_lang}")
            self.client = DirectTranslateClient(
                cache_file=self.client.cache_file,
                device=self.client.device,
                source_lang=source,
                target_lang=self.target_lang,
            )
            self.client.ensure_ready()
            # Update handlers with new client
            self.text_handler.client = self.client
            self.office_handler.client = self.client
            self.media_handler.client = self.client
            self.rename_proc.client = self.client

    def _process_content_for_file(self, path: Path) -> None:
        if not safe_is_file(path):
            return

        # Handle autodetection
        if self.auto_detect:
            snippet = self._get_content_snippet(path)
            if snippet:
                src_lang = detect_language(snippet)
                if src_lang == self.target_lang:
                    self._stats_inc("files_content_skipped")
                    return
                self._ensure_client_lang(src_lang)

        s, ok, t = path.suffix.lower(), False, "skipped"
        if s in self.text_extensions:
            ok, t = self.text_handler.translate_text_inplace(path), "text"
        elif s in {".csv", ".tsv"}:
            ok, t = self.text_handler.translate_csv_inplace(path), "csv/tsv"
        elif s == ".json":
            ok, t = self.text_handler.translate_json_inplace(path), "json"
        elif s == ".docx":
            ok, t = self.office_handler.translate_docx_inplace(path), "docx"
        elif s == ".xlsx":
            ok, t = self.office_handler.translate_xlsx_inplace(path), "xlsx"
        elif s == ".pptx":
            ok, t = self.office_handler.translate_pptx_inplace(path), "pptx"
        elif self.translate_extract_sidecars and s in (
            {".pdf", ".vsd", ".vsdx"} | self.image_extensions
        ):
            self._process_sidecar(path, s)
            return
        if ok:
            self._stats_inc("files_content_translated")
            print(f"  Success: Content translated ({t}): {path.name}")
            self._maybe_rename_via_content(path)
        else:
            self._stats_inc("files_content_skipped")

    def _process_sidecar(self, path: Path, suf: str) -> None:
        text = None
        if suf == ".pdf":
            text = self.media_handler.extract_pdf_text(path)
            if not text or not is_russian(text):
                text = self.media_handler.extract_pdf_ocr_text(path)
        elif suf in (".vsd", ".vsdx"):
            text = self.media_handler.extract_vsd_text(path)
        elif suf in self.image_extensions:
            text = self.media_handler.extract_ocr_text(path)
        if text and is_russian(text):
            trans = self.text_handler.translate_text_if_russian(text)
            if trans:
                sidecar = path.with_suffix(path.suffix + ".en.txt")
                if not safe_exists(sidecar):
                    sidecar.write_text(trans, encoding="utf-8")
                    self._stats_inc("sidecars_written")
                    self._stats_inc("files_content_translated")
                    print(f"  Success: Sidecar written: {path.name}.en.txt")
                    return
        self._stats_inc("files_content_skipped")

    def run(self) -> None:
        print("=" * 70 + "\nRU→EN WORKSPACE TRANSLATOR\n" + "=" * 70)
        self.client.ensure_ready()
        t0 = time.time()
        if not self.upgrade_only:
            print("\nPASS 1: Renaming...")
            self.rename_proc.process_dirs_recursive(self.root_path, self._stats_inc)
        if not self.rename_only:
            print("\nPASS 2: Upgrading...")
            legacy = [
                p
                for p in self.root_path.rglob("*")
                if safe_is_file(p)
                and p.suffix.lower() in {".doc", ".xls", ".ppt", ".rtf", ".odt"}
            ]
            upgraded = sum(
                1
                for p in legacy
                if self.office_handler.upgrade_office_file(p, self._unique_path) != p
            )
            print(f"  Success: Upgraded {upgraded} legacy files")
        if not self.rename_only and not self.upgrade_only:
            print("\nPASS 3: Content...")
            [
                self._process_content_for_file(p)
                for p in self.root_path.rglob("*")
                if safe_is_file(p) and not p.name.startswith(".")
            ]
        print("\n" + "=" * 70 + f"\nDONE in {time.time() - t0:.2f}s\n" + "=" * 70)
