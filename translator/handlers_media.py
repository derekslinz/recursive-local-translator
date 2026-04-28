import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from .handlers_base import BaseHandler

try:
    import PyPDF2

    HAS_PDF = True
except ImportError:
    HAS_PDF = False


class MediaHandler(BaseHandler):
    def extract_msg_text(self, path: Path, limit_chars: int = 100000) -> Optional[str]:
        try:
            import extract_msg

            msg = extract_msg.Message(str(path))
            parts = []
            if msg.subject:
                parts.append(str(msg.subject))
            if msg.body:
                parts.append(str(msg.body))
            if getattr(msg, "htmlBody", None):
                parts.append(str(msg.htmlBody))
            text = "\n\n".join(p for p in parts if p and str(p).strip())
            if text:
                return text[:limit_chars]
        except ImportError:
            pass
        except Exception as e:
            with self.lock:
                print(f"  Warning: MSG extract error for {path.name}: {e}")
        return None

    def extract_djvu_text(self, path: Path, limit_chars: int = 100000) -> Optional[str]:
        try:
            res = subprocess.run(
                ["djvutxt", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if res.returncode == 0:
                text = res.stdout.decode(errors="ignore").strip()
                if text:
                    return text[:limit_chars]
        except Exception:
            pass
        return None

    def extract_vsd_text(self, path: Path, limit_chars: int = 20000) -> Optional[str]:
        try:
            res = subprocess.run(
                ["vsd2text", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if res.returncode == 0:
                text = res.stdout.decode(errors="ignore").strip()
                return text[:limit_chars] if text else None
        except Exception:
            pass
        return None

    def extract_ocr_text(self, path: Path) -> Optional[str]:
        # Method 1: tesseract CLI
        try:
            res = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "rus+eng"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if res.returncode == 0:
                text = res.stdout.decode(errors="ignore").strip()
                if text:
                    return text
        except Exception:
            pass

        # Method 2: EasyOCR
        try:
            import easyocr

            if not hasattr(self, "_easyocr_reader"):
                self._easyocr_reader = easyocr.Reader(["ru", "en"], gpu=True)
            result = self._easyocr_reader.readtext(str(path), detail=0, paragraph=True)
            if result:
                return "\n".join(result).strip()
        except ImportError:
            pass
        except Exception as e:
            with self.lock:
                print(f"  Warning: EasyOCR error for {path.name}: {e}")

        # Method 3: pytesseract
        try:
            import pytesseract
            from PIL import Image

            text = pytesseract.image_to_string(Image.open(path), lang="rus+eng")
            if text and text.strip():
                return text.strip()
        except ImportError:
            pass
        except Exception as e:
            with self.lock:
                print(f"  Warning: pytesseract error for {path.name}: {e}")

        return None

    def extract_pdf_ocr_text(self, path: Path) -> Optional[str]:
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="pdf_ocr_"))
            subprocess.run(
                ["pdftoppm", "-png", str(path), str(temp_dir / "page")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            pages_text = []
            for img_path in sorted(temp_dir.glob("page-*.png")):
                page_content = self.extract_ocr_text(img_path)
                if page_content:
                    pages_text.append(page_content)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return "\n\n".join(pages_text) if pages_text else None
        except Exception as e:
            with self.lock:
                print(f"  Warning: PDF OCR error for {path.name}: {e}")
        return None

    def extract_pdf_text(self, path: Path, limit_chars: int = 100000) -> Optional[str]:
        # Method 1: PyMuPDF (fitz)
        try:
            import fitz

            with fitz.open(path) as doc:
                buf, total = [], 0
                for page in doc:
                    t = page.get_text() or ""
                    if t.strip():
                        buf.append(t)
                        total += len(t)
                        if total >= limit_chars:
                            break
                if buf:
                    return "\n".join(buf).strip()
        except ImportError:
            pass
        except Exception as e:
            with self.lock:
                print(f"  Warning: PyMuPDF error for {path.name}: {e}")

        # Method 2: PyPDF2
        if HAS_PDF:
            try:
                with path.open("rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    buf, total = [], 0
                    for page in reader.pages:
                        t = page.extract_text() or ""
                        if t.strip():
                            buf.append(t)
                            total += len(t)
                            if total >= limit_chars:
                                break
                    if buf:
                        return "\n".join(buf).strip()
            except Exception as e:
                with self.lock:
                    print(f"  Warning: PyPDF2 error for {path.name}: {e}")

        # Method 3: pdfminer.six
        try:
            from pdfminer.high_level import extract_text

            t = extract_text(str(path))
            if t and t.strip():
                return t[:limit_chars].strip()
        except ImportError:
            pass
        except Exception as e:
            with self.lock:
                print(f"  Warning: pdfminer error for {path.name}: {e}")

        # Method 4: pdftotext CLI
        try:
            res = subprocess.run(
                ["pdftotext", str(path), "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if res.returncode == 0:
                text = res.stdout.decode(errors="ignore").strip()
                if text:
                    return text[:limit_chars]
        except Exception:
            pass

        return None
