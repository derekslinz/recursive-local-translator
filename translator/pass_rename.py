import os
from pathlib import Path
from .translator_utils import (
    is_russian,
    sanitize_name,
    split_suffixes,
    safe_exists,
    safe_is_file,
    safe_is_dir,
    move_path,
    detect_language,
)


class RenameProcessor:
    def __init__(
        self,
        client,
        lock,
        unique_path_func,
        auto_detect=False,
        target_lang="en",
        dry_run=False,
        rename_log_callback=None,
    ):
        self.client = client
        self.lock = lock
        self.unique_path_func = unique_path_func
        self.auto_detect = auto_detect
        self.target_lang = target_lang
        self.dry_run = dry_run
        self.rename_log_callback = rename_log_callback

    def _should_translate(self, text: str) -> bool:
        if not text:
            return False
        if self.auto_detect:
            lang = detect_language(text)
            return lang != self.target_lang
        return is_russian(text)

    def translate_filename(self, filename: str) -> str:
        if not filename or filename in (".", "..") or filename.startswith("."):
            return filename
        stem, suf = split_suffixes(filename)
        new_stem = (
            sanitize_name(self.client.translate(stem))
            if self._should_translate(stem)
            else sanitize_name(stem)
        )
        new_stem = new_stem or stem
        full = f"{new_stem}{suf}"
        while len(os.fsencode(full)) > 255:
            new_stem = new_stem[:-1].rstrip()
            if not new_stem:
                return filename[:255] if len(os.fsencode(filename)) > 255 else filename
            full = f"{new_stem}{suf}"
        return full

    def merge_dir_into(self, src_dir: Path, dst_dir: Path, stats_callback) -> None:
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        try:
            items = list(src_dir.iterdir())
        except OSError:
            return
        for item in items:
            if safe_is_dir(item):
                dst_child = dst_dir / item.name
                if safe_exists(dst_child) and safe_is_dir(dst_child):
                    self.merge_dir_into(item, dst_child, stats_callback)
                    try:
                        item.rmdir()
                    except OSError:
                        pass
                else:
                    final_dst = self.unique_path_func(dst_child)
                    move_path(item, final_dst)
                    print(
                        f"  Success: Moved directory: {item.relative_to(src_dir)} → {final_dst.relative_to(dst_dir.parent)}"
                    )
                    stats_callback("items_moved")
            else:
                new_name = self.translate_filename(item.name)
                target = dst_dir / new_name
                if safe_exists(target):
                    target = self.unique_path_func(target)
                if new_name != item.name:
                    stats_callback("files_renamed")
                    print(f"  Success: Renamed file: {item.name} → {target.name}")
                move_path(item, target)
                if new_name == item.name:
                    print(
                        f"  Success: Moved file: {item.name} → {target.relative_to(dst_dir.parent)}"
                    )
                stats_callback("items_moved")

    def process_dirs_recursive(self, current: Path, stats_callback) -> None:
        try:
            items = sorted(current.iterdir())
        except OSError:
            return
        for f in (p for p in items if safe_is_file(p)):
            if f.name.startswith(".") or f.name.startswith("~$"):
                continue
            new_name = self.translate_filename(f.name)
            if new_name != f.name:
                target = self.unique_path_func(current / new_name)
                if self.dry_run:
                    print(f"  Would rename: {f.name} → {target.name}")
                else:
                    stats_callback("files_renamed")
                    move_path(f, target)
                    print(f"  Success: Renamed file: {f.name} → {target.name}")
                    stats_callback("items_moved")
                    if self.rename_log_callback:
                        self.rename_log_callback(f, target)
        for d in (p for p in items if safe_is_dir(p)):
            if d.name.startswith("."):
                continue
            translated = (
                sanitize_name(self.client.translate(d.name))
                if self._should_translate(d.name)
                else d.name
            )
            if translated == d.name:
                self.process_dirs_recursive(d, stats_callback)
                continue
            if self.dry_run:
                print(f"  Would rename dir: {d.name} → {translated}")
                self.process_dirs_recursive(d, stats_callback)
                continue
            new_path = d.parent / translated
            if safe_exists(new_path):
                print(f"  ⊘ Directory exists: {translated} (merging)")
                stats_callback("dirs_existing_merged")
            else:
                new_path.mkdir(parents=True, exist_ok=True)
                print(f"  Success: Renamed directory: {d.name} → {translated}")
                stats_callback("dirs_created")
            self.merge_dir_into(d, new_path, stats_callback)
            self.process_dirs_recursive(new_path, stats_callback)
            try:
                d.rmdir()
            except OSError:
                pass
