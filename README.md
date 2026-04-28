# Recursive Local Translator

A high-performance, modular workspace translator designed to handle massive directories with mixed file formats. It leverages **CTranslate2** for ultra-fast inference and supports **CUDA** (NVIDIA) and **MPS** (Apple Silicon) hardware acceleration.

## Key Capabilities

- **Recursive Workspace Translation**: Translates both directory names and filenames.
- **In-place Content Translation**:
  - **Text-based**: `.txt`, `.md`, `.log`, `.rst`, `.cfg`, `.conf`, `.tex`, `.yaml`, `.yml`, `.xml`, `.html`
  - **Structured Data**: `.csv`, `.json`
  - **Office Documents**: `.docx`, `.xlsx`, `.pptx` (preserves formatting)
- **Sidecar Extracts**: Generates `.en.txt` translations for `.pdf`, `.vsd`, `.vsdx`, and images (via OCR).
- **Format Upgrading**: Automatically converts legacy Office formats (`.doc`, `.xls`, `.ppt`, `.rtf`, `.odt`) to modern OpenXML formats using LibreOffice.
- **Language Intelligence**: Automatic language detection per file/folder with manual source/target language overrides.
- **Robustness**:
  - Persistent translation cache (SQLite) to avoid re-translating unchanged text.
  - Multi-threaded processing for speed.
  - Sanitization of filenames to prevent filesystem errors.

## Installation

### 1. Prerequisites

- **Python 3.8+**
- **LibreOffice** (required for the `--upgrade-only` pass or legacy format conversion)
- **Tesseract OCR** (optional, for image/PDF OCR)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Translation Models

This tool uses Argos Translate models. Install the required language pair (e.g., Russian to English):

```bash
argospm install translate-ru_en
```

## Usage

Basic usage (translates everything in the current directory from Russian to English):

```bash
python3 translate_all.py
```

### Common Flags

- `--root_path [PATH]`: Specify the directory to process (default: current).
- `--auto-detect`: Enable automatic language detection per file.
- `--source-lang [LANG]`: Override default source language (default: `ru`).
- `--target-lang [LANG]`: Specify target language (default: `en`).
- `--device [auto|cuda|cpu|mps]`: Force a specific hardware accelerator.
- `--rename-only`: Only translate filenames and directory names.
- `--upgrade-only`: Only convert legacy Office formats to modern ones.
- `--sidecars`: Generate sidecar text extracts for PDFs and images.
- `--workers [N]`: Number of concurrent threads (default: 5).

## Architecture

The project is modularized for maintainability:

- `translate_all.py`: CLI entry point and argument parsing.
- `translator_workspace.py`: Orchestrates the multi-pass translation process.
- `translate_client.py`: High-performance CTranslate2 client with SQLite caching.
- `pass_rename.py`: Specialized logic for filesystem object translation.
- `translator_utils.py`: Shared utilities for language detection and path sanitization.
- `handlers_*.py`: Format-specific translation handlers (Text, Office, Media).

## Security Note

Use with caution--inline translation is  irreversible. ALWAYS operate on a mirror of your source data. The only protections built in are that `.ini` files are automatically excluded from inline translation.

## License

MIT
