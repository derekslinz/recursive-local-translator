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
- Features: Language autodetection, manual source/target overrides, pass-specific execution.
- Excludes: .ini files to protect system configurations.
"""

import argparse
import sys
import traceback
from translator_workspace import WorkspaceRUENTranslator

def main():
    """Main entrypoint for the translation script."""
    # Reconfigure stdout/stderr to handle surrogate escapes in filenames
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(description="Translate Russian workspace to English.")
    parser.add_argument(
        "root_path",
        nargs="?",
        default=".",
        help="Root path to process (default: current directory)"
    )
    parser.add_argument("--sidecars", action="store_true", help="Write sidecar files for PDFs/images")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument(
        "--cache-file", type=str, default=".translation_cache.db", help="Path to translation cache"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu", "mps"],
        help="Device for inference (default: auto)",
    )
    parser.add_argument(
        "--source-lang",
        type=str,
        default="ru",
        help="Default source language (default: ru)"
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        default="en",
        help="Target language (default: en)"
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help="Automatically detect source language per file/folder"
    )
    parser.add_argument(
        "--rename-only",
        action="store_true",
        help="Only execute the file/folder rename pass"
    )
    parser.add_argument(
        "--upgrade-only",
        action="store_true",
        help="Only execute the file format upgrade pass"
    )

    args = parser.parse_args()

    try:
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
        )
        tr.run()
    except KeyboardInterrupt:
        print("\n⚠ Translation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
