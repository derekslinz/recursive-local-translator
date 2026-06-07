import builtins
import concurrent.futures
import os
import threading
import time
from pathlib import Path
from typing import Optional

from .translate_client import DirectTranslateClient
from .translator_utils import (
    is_russian,
    sanitize_name,
    needs_content_based_name,
    safe_exists,
    safe_is_file,
    detect_language,
    read_text_detected,
)
from .translation_log import TranslationLog
from .handlers_text import TextHandler
from .handlers_office import OfficeHandler
from .handlers_media import MediaHandler
from .handlers_email import EmailHandler
from .handlers_ebook import EbookHandler
from .pass_rename import RenameProcessor


class WorkspaceRUENTranslator:
    def __init__(self, root_path: str, **kwargs):
        self.root_path = Path(root_path)
        self._lock = threading.RLock()

        self.source_lang = kwargs.get("source_lang", "ru")
        self.target_lang = kwargs.get("target_lang", "en")
        self.auto_detect = kwargs.get("auto_detect", False)

        self.transliterate = kwargs.get("transliterate", False)
        self._glossary = kwargs.get("glossary") or {}
        self.client = DirectTranslateClient(
            cache_file=kwargs.get("cache_file", ".translation_cache.db"),
            device=kwargs.get("device", "auto"),
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            transliterate_only=self.transliterate,
            glossary=self._glossary,
        )
        self.rename_only = kwargs.get("rename_only", False)
        self.upgrade_only = kwargs.get("upgrade_only", False)
        self.workers = kwargs.get("workers", 5)
        self.skip_translated = kwargs.get("skip_translated", False)
        self.only_extensions: set = kwargs.get("only_extensions") or set()
        self.dry_run: bool = kwargs.get("dry_run", False)
        self.max_file_size: int = kwargs.get("max_file_size", 0)
        _log_file = kwargs.get("log_file")
        self._log: Optional[TranslationLog] = TranslationLog(_log_file) if _log_file and not self.dry_run else None
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
            ".jsonl",
            ".lrc",
            ".info",
            ".textile",
            ".strings",
        }
        self.image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

        self.text_handler = TextHandler(self.client, self._lock)
        self.office_handler = OfficeHandler(self.client, self._lock)
        self.media_handler = MediaHandler(self.client, self._lock)
        self.email_handler = EmailHandler(self.client, self._lock)
        self.ebook_handler = EbookHandler(self.client, self._lock)
        self.rename_proc = RenameProcessor(
            self.client,
            self._lock,
            self._unique_path,
            auto_detect=self.auto_detect,
            target_lang=self.target_lang,
            dry_run=self.dry_run,
            rename_log_callback=self._log_rename,
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
                "files_content_renamed",
                "sidecars_written",
                "sidecars_skipped",
            ]
        }

    def _stats_inc(self, key):
        with self._lock:
            self.stats[key] += 1

    def _log_rename(self, old: Path, new: Path) -> None:
        if self._log:
            self._log.log_rename(old, new)

    def _log_content(self, path: Path, kind: str) -> None:
        if self._log:
            self._log.log_content(path, kind)

    def _log_sidecar(self, source: Path, sidecar: Path) -> None:
        if self._log:
            self._log.log_sidecar(source, sidecar)

    def _print_stats(self) -> None:
        labels = {
            "dirs_created": "Directories renamed",
            "dirs_existing_merged": "Directories merged",
            "items_moved": "Items moved",
            "files_renamed": "Files renamed",
            "files_content_translated": "Files translated",
            "files_content_skipped": "Files skipped",
            "files_content_renamed": "Files renamed by content",
            "sidecars_written": "Sidecars written",
            "sidecars_skipped": "Sidecars skipped",
        }
        rows = [(labels[k], v) for k, v in self.stats.items() if v]
        if not rows:
            return
        print("\nSTATS:")
        w = max(len(label) for label, _ in rows)
        for label, count in rows:
            print(f"  {label:<{w}}  {count:,}")

    def _unique_path(self, path: Path) -> Path:
        with self._lock:
            if not safe_exists(path):
                return path
            suf, stem = path.suffix, path.stem
            while len(os.fsencode(stem)) > 250:
                stem = stem[:-1].rstrip()
            if not stem:
                return path  # suffix alone is too long; can't construct a valid unique name
            base, i = path.with_name(stem), 1
            while True:
                name = f"{base.name}-{i}{suf}"
                while len(os.fsencode(name)) > 255:
                    stem = base.name[:-1].rstrip()
                    if not stem:
                        return path  # can't shorten further
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
            print(f"    [Renamed via content]: {new_path.name}")
        except (OSError, ValueError):
            pass

    def _get_content_snippet(self, path: Path) -> Optional[str]:
        suf = path.suffix.lower()
        try:
            if suf in self.text_extensions:
                for line in read_text_detected(path).splitlines():
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
            print(f"  INFO: Switching language model: {source} -> {self.target_lang}")
            self.client = DirectTranslateClient(
                cache_file=self.client.cache_file,
                device=self.client.device,
                source_lang=source,
                target_lang=self.target_lang,
                transliterate_only=self.transliterate,
                glossary=self._glossary,
            )
            self.client.ensure_ready()
            # Update handlers with new client
            self.text_handler.client = self.client
            self.office_handler.client = self.client
            self.media_handler.client = self.client
            self.email_handler.client = self.client
            self.ebook_handler.client = self.client
            self.rename_proc.client = self.client

    def _is_qt_ts_file(self, path: Path) -> bool:
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:1024].lower().lstrip()
        except Exception:
            return False

        if head.startswith("<?xml"):
            decl_end = head.find("?>")
            if decl_end == -1:
                return False
            head = head[decl_end + 2 :].lstrip()

        return head.startswith("<ts") and (
            len(head) == 3 or head[3].isspace() or head[3] == ">"
        )

    def _process_content_for_file(self, path: Path) -> None:
        if not safe_is_file(path):
            return

        if self.skip_translated:
            try:
                stat = path.stat()
                if self.client.is_file_translated(str(path), stat.st_mtime, stat.st_size):
                    self._stats_inc("files_content_skipped")
                    return
            except OSError:
                pass

        if self.only_extensions and path.suffix.lower() not in self.only_extensions:
            return

        if self.max_file_size:
            try:
                if path.stat().st_size > self.max_file_size:
                    return
            except OSError:
                pass

        if self.dry_run:
            snippet = self._get_content_snippet(path)
            if snippet and is_russian(snippet):
                print(f"  Would translate ({path.suffix.lstrip('.')}): {path.name}")
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
        elif s == ".arb":
            ok, t = self.text_handler.translate_json_inplace(path), "arb"
        elif s == ".fb2":
            ok, t = self.text_handler.translate_fb2_inplace(path), "fb2"
        elif s == ".ts" and self._is_qt_ts_file(path):
            ok, t = self.text_handler.translate_xml_inplace(path), "qt-ts"
        elif s in {".resx", ".xliff", ".xlf", ".tmx", ".svg"}:
            ok, t = self.text_handler.translate_xml_inplace(path), "xml"
        elif s == ".docx":
            ok, t = self.office_handler.translate_docx_inplace(path), "docx"
        elif s == ".xlsx":
            ok, t = self.office_handler.translate_xlsx_inplace(path), "xlsx"
        elif s == ".pptx":
            ok, t = self.office_handler.translate_pptx_inplace(path), "pptx"
        elif s in {".ods", ".odp", ".odt"}:
            ok, t = self.office_handler.translate_odf_inplace(path), "odf"
        elif s == ".eml":
            ok, t = self.email_handler.translate_eml_inplace(path), "eml"
        elif s == ".epub":
            ok, t = self.ebook_handler.translate_epub_inplace(path), "epub"
        elif self.translate_extract_sidecars and s in (
            {".pdf", ".vsd", ".vsdx", ".msg", ".djvu"} | self.image_extensions
        ):
            self._process_sidecar(path, s)
            return
        if ok:
            self._stats_inc("files_content_translated")
            self._log_content(path, t)
            print(f"  Success: Content translated ({t}): {path.name}")
            self._maybe_rename_via_content(path)
            if self.skip_translated:
                try:
                    stat = path.stat()
                    self.client.mark_file_translated(str(path), stat.st_mtime, stat.st_size)
                except OSError:
                    pass
        else:
            self._stats_inc("files_content_skipped")

    def _process_sidecar(self, path: Path, suf: str) -> None:
        if self.skip_translated:
            try:
                stat = path.stat()
                if self.client.is_file_translated(str(path), stat.st_mtime, stat.st_size):
                    self._stats_inc("sidecars_skipped")
                    return
            except OSError:
                pass

        if self.dry_run:
            print(f"  Would extract sidecar: {path.name}")
            return

        if self.max_file_size:
            try:
                if path.stat().st_size > self.max_file_size:
                    return
            except OSError:
                pass

        text = None
        if suf == ".pdf":
            text = self.media_handler.extract_pdf_text(path)
            if not text or not is_russian(text):
                text = self.media_handler.extract_pdf_ocr_text(path)
        elif suf in (".vsd", ".vsdx"):
            text = self.media_handler.extract_vsd_text(path)
        elif suf == ".msg":
            text = self.media_handler.extract_msg_text(path)
        elif suf == ".djvu":
            text = self.media_handler.extract_djvu_text(path)
        elif suf in self.image_extensions:
            text = self.media_handler.extract_ocr_text(path)
        if text and is_russian(text):
            trans = self.text_handler.translate_text_if_russian(text)
            if trans:
                sidecar = path.with_suffix(path.suffix + ".en.txt")
                if not safe_exists(sidecar):
                    sidecar.write_text(trans, encoding="utf-8")
                    self._stats_inc("sidecars_written")
                    self._log_sidecar(path, sidecar)
                    self._stats_inc("files_content_translated")
                    print(f"  Success: Sidecar written: {path.name}.en.txt")
                    if self.skip_translated:
                        try:
                            stat = path.stat()
                            self.client.mark_file_translated(str(path), stat.st_mtime, stat.st_size)
                        except OSError:
                            pass
                    return
        self._stats_inc("files_content_skipped")

    def run(self) -> None:
        from .translator_utils import move_path
        print("=" * 70 + "\nRU→EN WORKSPACE TRANSLATOR\n" + "=" * 70)
        self.client.ensure_ready()
        t0 = time.time()

        single_file = self.root_path.is_file()
        # For a single-file target, track the path across passes (rename can move it)
        current = self.root_path if single_file else None

        if not self.upgrade_only:
            print("\nPASS 1: Renaming...")
            if single_file:
                p = current
                if not p.name.startswith(".") and not p.name.startswith("~$"):
                    new_name = self.rename_proc.translate_filename(p.name)
                    if new_name != p.name:
                        target = self._unique_path(p.parent / new_name)
                        if self.dry_run:
                            print(f"  Would rename: {p.name} → {target.name}")
                        else:
                            move_path(p, target)
                            self._stats_inc("files_renamed")
                            self._stats_inc("items_moved")
                            print(f"  Success: Renamed file: {p.name} → {target.name}")
                            current = target
                            self._log_rename(p, current)
            else:
                self.rename_proc.process_dirs_recursive(self.root_path, self._stats_inc)

        if not self.rename_only:
            print("\nPASS 2: Upgrading...")
            if single_file:
                _legacy_exts = {".doc", ".xls", ".ppt", ".rtf", ".odt"}
                upgraded = 0
                if safe_is_file(current) and current.suffix.lower() in _legacy_exts:
                    if self.dry_run:
                        print(f"  Would upgrade: {current.name}")
                        upgraded = 1
                    else:
                        new_path = self.office_handler.upgrade_office_file(current, self._unique_path)
                        if new_path != current:
                            upgraded = 1
                            print(f"  Success: Upgraded file: {current.name} → {new_path.name}")
                            current = new_path
                print(f"  Success: Upgraded {upgraded} legacy files")
            else:
                legacy = [
                    p
                    for p in self.root_path.rglob("*")
                    if safe_is_file(p)
                    and p.suffix.lower() in {".doc", ".xls", ".ppt", ".rtf", ".odt"}
                ]
                if self.dry_run:
                    for p in legacy:
                        print(f"  Would upgrade: {p.name}")
                    upgraded = len(legacy)
                else:
                    upgraded = 0
                    for p in legacy:
                        new_path = self.office_handler.upgrade_office_file(p, self._unique_path)
                        if new_path != p:
                            upgraded += 1
                            print(f"  Success: Upgraded file: {p.name} → {new_path.name}")
                print(f"  Success: Upgraded {upgraded} legacy files")

        if not self.rename_only and not self.upgrade_only:
            print("\nPASS 3: Content...")
            if single_file:
                files = [current] if safe_is_file(current) else []
            else:
                files = [
                    p for p in self.root_path.rglob("*")
                    if safe_is_file(p) and not p.name.startswith(".")
                ]
            try:
                from tqdm import tqdm as _tqdm
                _tqdm_available = True
            except ImportError:
                _tqdm_available = False

            _orig_print = builtins.print
            if _tqdm_available:
                builtins.print = _tqdm.write
            try:
                if self.auto_detect or self.workers <= 1:
                    it = _tqdm(files, desc="Content", unit="file") if _tqdm_available else files
                    for p in it:
                        self._process_content_for_file(p)
                else:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
                        future_to_path = {pool.submit(self._process_content_for_file, p): p for p in files}
                        it = _tqdm(
                            concurrent.futures.as_completed(future_to_path),
                            total=len(future_to_path),
                            desc="Content",
                            unit="file",
                        ) if _tqdm_available else concurrent.futures.as_completed(future_to_path)
                        for fut in it:
                            exc = fut.exception()
                            if exc:
                                print(f"  Warning: Worker error for {future_to_path[fut].name}: {exc}")
            finally:
                builtins.print = _orig_print
        self._print_stats()
        print("\n" + "=" * 70 + f"\nDONE in {time.time() - t0:.2f}s\n" + "=" * 70)
        if self._log:
            self._log.close()
