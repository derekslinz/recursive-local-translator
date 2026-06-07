#!/usr/bin/env python3
"""
Multi-language workspace translator with CUDA and MPS acceleration (Argos Translate)

Capabilities:
- Translate directory names and filenames.
- Upgrade legacy Office formats (.doc, .xls, .ppt, .rtf, .odt) to modern formats.
- Inline content translation for:
    - Text: .txt, .md, .log, .rst, .cfg, .conf, .tex, .yaml, .yml, .xml, .html
    - Data: .csv, .json
    - Office: .docx, .xlsx, .pptx
- Sidecar extracts (.en.txt) for: .pdf, .vsd, .vsdx, and images (via OCR).
    - Data: .csv, .json, .arb
    - Office: .docx, .xlsx, .pptx, .odt, .ods, .odp
    - Email / ebook: .eml, .epub, .fb2
    - Sidecar extracts (.en.txt) for: .pdf, .vsd, .vsdx, .msg, .djvu, and images (via OCR).
- Features: Language autodetection, manual source/target overrides, pass-specific execution, transliteration mode.
- Excludes: .ini files to protect system configurations.
"""

import argparse
import sys
import traceback
from translator.translator_workspace import WorkspaceRUENTranslator


def main():
    """Main entrypoint for the translation script."""
    # Reconfigure stdout/stderr to handle surrogate escapes in filenames
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Execution Passes:
  1. Renaming: Recursively renames directories and files using the translator or transliterator.
  2. Upgrading: Converts legacy Office formats (.doc, .xls, .ppt, .rtf, .odt) to modern OpenXML.
  3. Content: Translates supported text, data, and office content in-place.
  4. Sidecars: Generates .en.txt extracts for PDF and Image files using OCR fallbacks.
     Also supports sidecars for MSG and DJVU extraction.

Examples:
  Translate current workspace using CUDA:
    python3 translate_all.py . --device cuda

  Only rename files/folders in current directory (transliteration mode):
    python3 translate_all.py . --rename-only --transliterate

  Process specific directory with 10 threads and OCR sidecars:
    python3 translate_all.py /my/data --workers 10 --sidecars
        """,
    )
    parser.add_argument(
        "root_path",
        help="Target directory to process recursively",
    )
    parser.add_argument(
        "--sidecars",
        action="store_true",
        help="Generate sidecar .en.txt files for PDFs and images instead of in-place translation",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Max concurrent threads for translation (default: 5)",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=".translation_cache.db",
        help="SQLite database for persistent translation caching (default: .translation_cache.db)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu", "mps"],
        help="Hardware accelerator to use (typically auto-detected). Options: 'cuda' (NVIDIA), 'mps' (Apple), 'cpu', or 'auto'",
    )
    parser.add_argument(
        "--source-lang",
        type=str,
        default="ru",
        help="Base source language code (default: 'ru')",
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        default="en",
        help="Desired target language code (default: 'en')",
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help="Enable per-file language detection (useful for mixed-language workspaces)",
    )
    parser.add_argument(
        "--rename-only",
        action="store_true",
        help="Skip content translation and only execute the file/folder rename pass",
    )
    parser.add_argument(
        "--upgrade-only",
        action="store_true",
        help="Skip all translation and only convert legacy Office formats to modern ones",
    )
    parser.add_argument(
        "--transliterate",
        action="store_true",
        help="Convert Cyrillic to Latin script without semantic translation (extremely fast)",
    )
    parser.add_argument(
        "--skip-translated",
        action="store_true",
        help="Skip files already translated in a previous run (tracked in the cache database)",
    )
    parser.add_argument(
        "--glossary",
        type=str,
        default=None,
        metavar="PATH",
        help="JSON file mapping source-language terms to forced target translations",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        metavar="EXTS",
        help="Comma-separated extensions to process in PASS 3 (e.g. txt,json,docx); all others skipped",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all files even if already translated (overrides auto-resume when cache DB exists)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview renames and content changes without writing any files",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Write a JSONL audit log of all renames and translations to PATH",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=0,
        metavar="BYTES",
        help="Skip files larger than BYTES in PASS 3 (0 = no limit; e.g. 10485760 for 10 MB)",
    )

    args = parser.parse_args()

    try:
        from pathlib import Path as _Path
        glossary = {}
        if args.glossary:
            import json as _json
            with open(args.glossary, encoding="utf-8") as _f:
                glossary = _json.load(_f)

        # Auto-enable skip-translated when resuming an existing cache DB
        skip_translated = args.skip_translated
        if not skip_translated and not args.force and _Path(args.cache_file).exists():
            skip_translated = True
            print(f"  ℹ Resuming: {args.cache_file} found — skip-translated auto-enabled (use --force to reprocess all)")

        only_extensions = (
            {("." + e.lstrip(".")).lower() for e in args.only.split(",")}
            if args.only else set()
        )

        tr = WorkspaceRUENTranslator(
            root_path=args.root_path,
            translate_extract_sidecars=args.sidecars,
            workers=args.workers,
            cache_file=args.cache_file,
            device=args.device,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            auto_detect=args.auto_detect,
            rename_only=args.rename_only,
            upgrade_only=args.upgrade_only,
            transliterate=args.transliterate,
            skip_translated=skip_translated,
            glossary=glossary,
            only_extensions=only_extensions,
            dry_run=args.dry_run,
            log_file=args.log_file,
            max_file_size=args.max_file_size,
        )
        tr.run()
    except KeyboardInterrupt:
        print("\nWarning: Translation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
