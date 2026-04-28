# Recursive Local Translator

A high-performance, modular workspace translator designed to handle massive directories with mixed file formats. It leverages **CTranslate2** for ultra-fast inference and supports **CUDA** (NVIDIA) and **MPS** (Apple Silicon) hardware acceleration.

Unlike simple wrappers, this tool drives the underlying translation models directly, providing significant speed improvements and better control over memory and device utilization.

---

## Key Capabilities

### 1. Multi-Pass Workspace Processing
The tool operates in three distinct phases to ensure consistency and safety:
- **Pass 1: Renaming**: Recursively translates directory names and filenames.
- **Pass 2: Upgrading**: Converts legacy Office formats (e.g., `.doc`) to modern OpenXML (`.docx`) using LibreOffice.
- **Pass 3: Content**: Performs in-place translation of file contents or generates sidecar text extracts.

### 2. Comprehensive Format Support
| Category | Supported Extensions |
| :--- | :--- |
| **Documentation** | `.txt`, `.log`, `.nfo`, `.md`, `.mdx`, `.rmd`, `.rst`, `.adoc`, `.org`, `.wiki`, `.rtx`, `.tex` |
| **Config / Web** | `.cfg`, `.conf`, `.toml`, `.properties`, `.mak`, `.cmake`, `.yaml`, `.yml`, `.xml`, `.html`, `.htm`, `.xhtml`, `.shtml`, `.json`, `.json5`, `.jsonc`, `.jsonl`, `.svg`, `.resx`, `.xliff`, `.xlf`, `.tmx` |
| **Subtitles** | `.srt`, `.vtt`, `.ass`, `.ssa`, `.sub`, `.sbv`, `.po`, `.pot` |
| **Additional Text** | `.lrc`, `.info`, `.textile`, `.strings`, `.arb`, `.fb2`, `.ts` (Qt XML autodetected only) |
| **Office** | `.docx`, `.xlsx`, `.pptx` (formatting preserved) |
| **OpenDocument** | `.odt`, `.ods`, `.odp` (native in-place translation) |
| **Email / Ebook** | `.eml` (subject/body + Base64 text-like attachments), `.epub` |
| **Sidecars** | `.pdf`, `.vsd`, `.vsdx`, `.msg`, `.djvu`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` (generates `.en.txt`) |

### 3. Intelligent Content Handling
- **Mixed Language Support**: Automatically detects language per paragraph/chunk. English text within a Russian document is preserved untouched.
- **Transliteration Mode**: High-speed mode to convert Cyrillic script to Latin script without full semantic translation.
- **Content-Based Renaming**: Can automatically rename generic filenames (like `scan_001.jpg` or `Untitled.txt`) based on the translated content found inside the file.

---

## Installation

### 1. Prerequisites
- **Python 3.8 - 3.12** (Python 3.13+ currently has limited ML library support).
- **LibreOffice**: Required for format upgrades (`.doc` → `.docx`).
- **Tesseract OCR**: Required for image and PDF OCR fallback.

### 2. Setup
It is highly recommended to use a virtual environment to manage dependencies:

```bash
# Clone the repository
git clone https://github.com/derekslinz/recursive-local-translator.git
cd recursive-local-translator

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the Russian-English translation model
argospm install translate-ru_en
```

> [!TIP]
> **Hardware Acceleration**: Manual device selection via `--device` is typically **not necessary**. The tool automatically detects and utilizes the best available accelerator (CUDA on NVIDIA GPUs, MPS on Apple Silicon) and falls back to CPU only if needed.

---

## Usage Guide

### Basic Command
Translates a specific directory from Russian to English (use `.` for the current directory):
```bash
python3 translate_all.py /path/to/workspace
```

### Advanced Flags
| Argument | Description |
| :--- | :--- |
| `root_path` | **Required**: The target directory to process recursively. |
| `--transliterate` | **Fast Mode**: Only converts Cyrillic to Latin (e.g., `Папка` → `Papka`). |
| `--auto-detect` | Detects language per file. Skips files that are already in the target language. |
| `--rename-only` | Only renames files and folders; skips content translation. |
| `--upgrade-only` | Only converts legacy formats; skips all translation. |
| `--sidecars` | Enables generating `.en.txt` extracts for binary formats (PDF, Images). |
| `--device [auto/cuda/mps/cpu]` | Forces a specific hardware accelerator (typically auto-detected). |
| `--workers [N]` | Sets concurrency level (default: 5). |

---

## Important Notes
- **Irreversible**: Content translation is performed **in-place**. ALWAYS work on a copy/mirror of your data.
- **Encoding**: The tool assumes UTF-8 encoding. Non-compliant files are processed with "surrogateescape" error handling to prevent crashes.

---

---

## Robustness & Reliability

### Cascading Fallbacks
To ensure maximum extraction success, the tool uses a cascading fallback strategy:
- **PDF Extraction**: `PyMuPDF` → `PyPDF2` → `pdfminer.six` → `pdftotext` (CLI).
- **OCR Engine**: `Tesseract` → `EasyOCR` → `pytesseract`.

### Email Attachment Handling (`.eml`)

- Base64-encoded attachments are decoded before processing.
- Text-like attachments (for example `.txt`, `.csv`, `.json`, `.xml`) are translated and re-encoded.
- Binary attachments are preserved untouched to avoid corruption.

### Filesystem Safety
- **Path Sanitization**: Automatically removes invalid characters and collapses excessive repetitions.
- **Length Enforcement**: Filenames are strictly limited to **255 bytes** using multi-byte safe truncation, preventing OS "path too long" errors.
- **Configuration Protection**: `.ini` and `.sys` files are automatically excluded from inline translation to prevent system corruption.

---


