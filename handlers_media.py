import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from translator_utils import is_russian
from handlers_base import BaseHandler

try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

class MediaHandler(BaseHandler):
    def extract_vsd_text(self, path: Path, limit_chars: int = 20000) -> Optional[str]:
        try:
            res = subprocess.run(["vsd2text", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if res.returncode == 0:
                text = res.stdout.decode(errors="ignore").strip()
                return text[:limit_chars] if text else None
        except Exception: pass
        return None

    def extract_ocr_text(self, path: Path) -> Optional[str]:
        try:
            res = subprocess.run(["tesseract", str(path), "stdout", "-l", "rus+eng"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if res.returncode == 0:
                return res.stdout.decode(errors="ignore").strip()
        except Exception as e:
            with self.lock: print(f"  Warning: OCR error for {path.name}: {e}")
        return None

    def extract_pdf_ocr_text(self, path: Path) -> Optional[str]:
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="pdf_ocr_"))
            subprocess.run(["pdftoppm", "-png", str(path), str(temp_dir / "page")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            pages_text = []
            for img_path in sorted(temp_dir.glob("page-*.png")):
                page_content = self.extract_ocr_text(img_path)
                if page_content: pages_text.append(page_content)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return "\n\n".join(pages_text) if pages_text else None
        except Exception as e:
            with self.lock: print(f"  Warning: PDF OCR error for {path.name}: {e}")
        return None

    def extract_pdf_text(self, path: Path, limit_chars: int = 100000) -> Optional[str]:
        if not HAS_PDF: return None
        try:
            with path.open("rb") as f:
                reader = PyPDF2.PdfReader(f)
                buf, total = [], 0
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        buf.append(t)
                        total += len(t)
                        if total >= limit_chars: break
                return "\n".join(buf).strip() or None
        except Exception: return None
